"""Pruebas de la extracción de adjuntos.

Los archivos se generan aquí mismo: las pruebas no dependen de un PDF de
ejemplo en el repositorio y cada caso pone justo el contenido que necesita.
"""

from __future__ import annotations

import io

import pytest

from app.services.attachments import (
    AttachmentExtractionError,
    AttachmentTooLargeError,
    UnsupportedAttachmentError,
    enrich_transcript,
    extract_text,
)

SIN_TOPES = {"max_bytes": 10_000_000, "max_chars": 20_000}


def _pdf(texto: str) -> bytes:
    """PDF mínimo de una página con el texto dado.

    Se construye a mano en vez de con reportlab para no añadir una dependencia
    al proyecto solo para fabricar material de prueba. El `xref` se calcula
    porque pypdf lo necesita para reconstruir la página.
    """
    contenido = f"BT /F1 12 Tf 72 720 Td ({texto}) Tj ET".encode("latin-1")

    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n" % len(contenido) + contenido + b"\nendstream",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for numero, cuerpo in enumerate(objetos, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n" % numero + cuerpo + b"\nendobj\n"

    inicio_xref = len(pdf)
    pdf += b"xref\n0 %d\n" % (len(objetos) + 1)
    pdf += b"0000000000 65535 f \n"
    for offset in offsets:
        pdf += b"%010d 00000 n \n" % offset
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objetos) + 1,
        inicio_xref,
    )
    return bytes(pdf)


def _docx(parrafos: list[str]) -> bytes:
    from docx import Document

    documento = Document()
    for parrafo in parrafos:
        documento.add_paragraph(parrafo)
    buffer = io.BytesIO()
    documento.save(buffer)
    return buffer.getvalue()


# --- Extracción --------------------------------------------------------------


def test_se_extrae_el_texto_de_un_pdf() -> None:
    contenido = _pdf("Especificacion de la pasarela de pagos")

    texto = extract_text(filename="especificacion.pdf", content=contenido, **SIN_TOPES)

    assert "pasarela de pagos" in texto


def test_se_extrae_el_texto_de_un_word() -> None:
    contenido = _docx(["Alcance acordado", "Incluye cobros y devoluciones"])

    texto = extract_text(filename="alcance.docx", content=contenido, **SIN_TOPES)

    assert "Alcance acordado" in texto
    assert "devoluciones" in texto


def test_una_extension_no_soportada_se_rechaza() -> None:
    with pytest.raises(UnsupportedAttachmentError) as error:
        extract_text(filename="hoja.xlsx", content=b"cualquier cosa", **SIN_TOPES)

    assert error.value.filename == "hoja.xlsx"


def test_un_pdf_corrupto_se_reporta_como_error_de_extraccion() -> None:
    with pytest.raises(AttachmentExtractionError) as error:
        extract_text(filename="roto.pdf", content=b"%PDF-1.4 no soy un pdf", **SIN_TOPES)

    assert error.value.filename == "roto.pdf"


def test_un_archivo_que_supera_el_tope_de_bytes_se_rechaza() -> None:
    with pytest.raises(AttachmentTooLargeError):
        extract_text(
            filename="grande.pdf",
            content=b"x" * 100,
            max_bytes=10,
            max_chars=1_000,
        )


def test_el_texto_se_trunca_al_maximo_de_caracteres() -> None:
    contenido = _pdf("y" * 400)

    texto = extract_text(
        filename="largo.pdf", content=contenido, max_bytes=10_000_000, max_chars=50
    )

    assert len(texto) <= 50


def test_un_sin_texto_extraible_devuelve_cadena_vacia() -> None:
    """Un PDF escaneado es legal; lo relevante es que no rompa la estimación."""
    texto = extract_text(filename="escaneado.pdf", content=_pdf(" "), **SIN_TOPES)

    assert texto.strip() == ""


# --- Enriquecimiento de la transcripción -------------------------------------


def test_sin_adjuntos_la_transcripcion_no_cambia() -> None:
    resultado = enrich_transcript(transcript="Hablamos del portal.", attachments=[])

    assert resultado == "Hablamos del portal."


def test_cada_adjunto_va_entre_sus_vallas_y_con_su_nombre() -> None:
    resultado = enrich_transcript(
        transcript="Hablamos del portal.",
        attachments=[("especificacion.pdf", "Trece milestones.")],
    )

    assert resultado.startswith("Hablamos del portal.")
    assert "--- attachment: especificacion.pdf ---" in resultado
    assert "--- end attachment ---" in resultado
    assert "Trece milestones." in resultado


def test_varios_adjuntos_producen_varios_bloques() -> None:
    resultado = enrich_transcript(
        transcript="Hablamos del portal.",
        attachments=[
            ("especificacion.pdf", "Texto del PDF."),
            ("alcance.docx", "Texto del Word."),
        ],
    )

    assert resultado.count("--- end attachment ---") == 2
    assert "attachment: especificacion.pdf" in resultado
    assert "attachment: alcance.docx" in resultado


def test_un_adjunto_sin_texto_no_crea_un_bloque_vacio() -> None:
    resultado = enrich_transcript(
        transcript="Hablamos del portal.",
        attachments=[("escaneado.pdf", "   ")],
    )

    assert resultado == "Hablamos del portal."