"""Extracción de texto de los adjuntos y su fusión con la transcripción.

El binario no se sube al proveedor: se extrae aquí y el texto viaja en el
prompt. Así el mismo camino sirve para OpenAI y para Anthropic, el
comportamiento es idéntico con y sin red, y el texto queda normalizado para el
chunking del módulo de RAG. Lo que se pierde es el layout visual, y la
estimación se apoya en el texto.

Los imports de pypdf y docx son perezosos a propósito: son las dos
dependencias más pesadas del proyecto y solo hacen falta si llega un adjunto.
"""

from __future__ import annotations

import io
import logging
from pathlib import PurePosixPath

logger = logging.getLogger(__name__)

_EXTS = {".pdf", ".docx"}


class AttachmentExtractionError(Exception):
    """No se pudo leer un adjunto soportado (PDF corrupto, Word ilegible)."""

    def __init__(self, filename: str, message: str) -> None:
        super().__init__(message)
        self.filename = filename
        self.message = message


class UnsupportedAttachmentError(AttachmentExtractionError):
    """La extensión del adjunto no es una que sepamos extraer."""


class AttachmentTooLargeError(AttachmentExtractionError):
    """El archivo supera el tope de bytes permitido.

    Existe separada de las demás porque se comprueba antes de leer el
    contenido: sin este tope, un PDF enorme se carga entero en memoria aunque su
    texto se recorte después.
    """


def _ext(filename: str) -> str:
    return PurePosixPath(filename).suffix.lower()


def _texto_pdf(content: bytes) -> str:
    """Texto del PDF, página a página.

    Una página que no se puede leer no tumba el documento entero: se registra y
    se sigue, porque en un PDF real alguna página ilegible es más probable que
    un archivo entero roto.
    """
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    partes: list[str] = []
    for pagina in reader.pages:
        try:
            texto = pagina.extract_text() or ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("No se pudo extraer el texto de una página: %s", exc)
            continue
        if texto.strip():
            partes.append(texto)
    return "\n\n".join(partes)


def _texto_docx(content: bytes) -> str:
    from docx import Document

    documento = Document(io.BytesIO(content))
    return "\n".join(p.text for p in documento.paragraphs if p.text and p.text.strip())


def extract_text(*, filename: str, content: bytes, max_bytes: int, max_chars: int) -> str:
    """Devuelve el texto del adjunto, acotado por tamaño y por longitud.

    `max_bytes` acota el archivo y se comprueba antes de procesar nada;
    `max_chars` acota lo que llega al prompt. Son dos topes distintos porque
    atacan riesgos distintos: uno protege el proceso y el otro, el contexto.

    Un texto vacío no es un error: un PDF escaneado sin capa de texto es
    perfectamente legal y lo único razonable es ignorarlo dejando constancia.
    """
    ext = _ext(filename)

    if ext not in _EXTS:
        raise UnsupportedAttachmentError(
            filename,
            f"Extensión {ext!r} no soportada; admitidas: {sorted(_EXTS)}.",
        )

    if len(content) > max_bytes:
        raise AttachmentTooLargeError(
            filename,
            f"El adjunto ocupa {len(content)} bytes y el máximo por archivo es {max_bytes}.",
        )

    try:
        texto = _texto_pdf(content) if ext == ".pdf" else _texto_docx(content)
    except AttachmentExtractionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AttachmentExtractionError(
            filename, f"No se pudo extraer el texto de {filename}: {exc}"
        ) from exc

    texto = texto.strip()
    if not texto:
        logger.info("El adjunto %s no contiene texto extraíble", filename)
        return ""

    if len(texto) > max_chars:
        logger.info(
            "Texto de %s truncado: se conservan %d caracteres de %d",
            filename,
            max_chars,
            len(texto),
        )
        texto = texto[:max_chars]

    return texto


def enrich_transcript(*, transcript: str, attachments: list[tuple[str, str]]) -> str:
    """Concatena la transcripción con un bloque delimitado por adjunto.

    Las vallas existen para que el modelo distinga la transcripción de la
    documentación y de qué archivo procede cada bloque. Sin ellas, el material
    adjunto se lee como si fuera parte de lo que se dijo en la reunión, que es
    justo la confusión que este endpoint existe para evitar.
    """
    utiles = [(nombre, texto) for nombre, texto in attachments if texto and texto.strip()]
    if not utiles:
        return transcript

    partes = [transcript.strip()]
    for nombre, texto in utiles:
        partes.append(
            f"--- attachment: {nombre} ---\n{texto.strip()}\n--- end attachment ---"
        )
    return "\n\n".join(partes)