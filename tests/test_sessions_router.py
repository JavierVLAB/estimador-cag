"""Pruebas del router de sesiones.

Ni el proveedor ni el extractor se llaman de verdad: se sustituyen por dobles.
Lo que se comprueba aquí es el contrato HTTP, el encadenado del turno y el
estado que queda en la sesión.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.schemas.session import ProjectMetadata
from app.main import app
from app.routers import sessions as sessions_router
from app.services import llm_service, metadata

CAMPOS = {
    "project_type": "web_saas",
    "detail_level": "medium",
    "output_format": "phases_table",
}


@pytest.fixture(autouse=True)
def store_limpio() -> None:
    """Cada test empieza sin sesiones y con un límite conocido."""
    sessions_router._store.clear()
    sessions_router._store._max_turns = 3


@pytest.fixture
def cliente() -> TestClient:
    """Usa la app montada, no el router suelto, para cubrir también el prefijo."""
    return TestClient(app)


class _GeneradorFalso:
    """Sustituto de `generate_turn` que responde con un texto fijo.

    Lo usan tanto la estimación como el extractor de metadata, así que separa
    las llamadas: el extractor es el único que fija `max_output_tokens`.
    """

    def __init__(self, texto: str = "Estimación de prueba.") -> None:
        self.texto = texto
        self.llamadas: list[dict] = []

    @property
    def estimaciones(self) -> list[dict]:
        return [c for c in self.llamadas if "max_output_tokens" not in c]

    @property
    def extracciones(self) -> list[dict]:
        return [c for c in self.llamadas if "max_output_tokens" in c]

    def __call__(self, *, system_prompt: str, messages: list[dict], **kwargs):
        self.llamadas.append({"system": system_prompt, "messages": list(messages), **kwargs})
        return llm_service.CompletionResult(
            text=self.texto,
            model="gpt-4o-mini",
            provider="openai",
            usage=llm_service.TokenUsage(
                input_tokens=100, output_tokens=50, total_tokens=150
            ),
        )


@pytest.fixture
def generador(monkeypatch: pytest.MonkeyPatch) -> _GeneradorFalso:
    falso = _GeneradorFalso()
    monkeypatch.setattr(llm_service, "generate_turn", falso)
    return falso


@pytest.fixture
def extractor(monkeypatch: pytest.MonkeyPatch):
    """Sustituye el extractor devolviendo una metadata fija o heredada."""

    def instalar(actualizada: ProjectMetadata | None = None):
        def falso(*, transcript, previous_metadata, conversation="", **kwargs):
            return (actualizada or ProjectMetadata()).merge_with(previous_metadata) if (
                actualizada is not None
            ) else previous_metadata

        monkeypatch.setattr(metadata, "extract_and_merge", falso)
        return falso

    return instalar


def _crear(cliente: TestClient) -> str:
    respuesta = cliente.post("/api/v1/sessions")
    assert respuesta.status_code == 201
    return respuesta.json()["session_id"]


# --- Ciclo de vida de la sesión ----------------------------------------------


def test_crear_una_sesion_devuelve_201_y_un_identificador(cliente) -> None:
    respuesta = cliente.post("/api/v1/sessions")

    assert respuesta.status_code == 201
    assert respuesta.json()["session_id"]


def test_una_sesion_nueva_esta_vacia(cliente) -> None:
    session_id = _crear(cliente)

    cuerpo = cliente.get(f"/api/v1/sessions/{session_id}").json()

    assert cuerpo["message_count"] == 0
    assert cuerpo["metadata"]["project_name"] is None


def test_consultar_una_sesion_inexistente_devuelve_404(cliente) -> None:
    respuesta = cliente.get("/api/v1/sessions/no-existe")

    assert respuesta.status_code == 404
    assert "no-existe" in respuesta.json()["detail"]


def test_consultar_una_sesion_no_llama_al_proveedor(cliente, generador) -> None:
    session_id = _crear(cliente)

    cliente.get(f"/api/v1/sessions/{session_id}")

    assert generador.llamadas == []


# --- Turno de estimación -----------------------------------------------------


def test_el_primer_turno_devuelve_la_estimacion(cliente, generador) -> None:
    session_id = _crear(cliente)

    respuesta = cliente.post(f"/api/v1/sessions/{session_id}/estimate", data=CAMPOS, files={"description": (None, "Hablamos del portal.")})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["text"] == "Estimación de prueba."
    assert cuerpo["usage"]["total_tokens"] == 150
    assert cuerpo["turns_kept"] == 1


def test_el_turno_se_registra_en_el_historial(cliente, generador) -> None:
    session_id = _crear(cliente)

    cliente.post(f"/api/v1/sessions/{session_id}/estimate", data=CAMPOS, files={"description": (None, "Hablamos del portal.")})

    cuerpo = cliente.get(f"/api/v1/sessions/{session_id}").json()
    assert cuerpo["message_count"] == 2


def test_el_segundo_turno_envia_el_primero_en_el_historial(cliente, generador) -> None:
    session_id = _crear(cliente)
    cliente.post(f"/api/v1/sessions/{session_id}/estimate", data=CAMPOS, files={"description": (None, "Turno uno.")})

    cliente.post(f"/api/v1/sessions/{session_id}/estimate", data=CAMPOS, files={"description": (None, "Turno dos.")})

    mensajes = generador.estimaciones[1]["messages"]
    contenidos = [m["content"] for m in mensajes]
    assert len(contenidos) == 3
    # El turno anterior viaja ya renderizado, entre sus vallas.
    assert "Turno uno." in contenidos[0]
    assert "Estimación de prueba." == contenidos[1]
    assert "Turno dos." in contenidos[2]


def test_el_system_prompt_lleva_la_metadata_del_turno_anterior(cliente, generador, extractor) -> None:
    extractor(ProjectMetadata(project_name="Portal de reservas"))
    session_id = _crear(cliente)

    cliente.post(f"/api/v1/sessions/{session_id}/estimate", data=CAMPOS, files={"description": (None, "Turno uno.")})
    cliente.post(f"/api/v1/sessions/{session_id}/estimate", data=CAMPOS, files={"description": (None, "Turno dos.")})

    assert "Portal de reservas" in generador.estimaciones[1]["system"]


def test_turnar_en_una_sesion_inexistente_devuelve_404(cliente, generador) -> None:
    respuesta = cliente.post(
        "/api/v1/sessions/no-existe/estimate",
        data=CAMPOS,
        files={"description": (None, "Hola.")},
    )

    assert respuesta.status_code == 404
    assert generador.llamadas == []


def test_la_metadata_llega_al_prompt_del_turno_siguiente(cliente, generador, extractor) -> None:
    """Regresión: el bloque se renderiza en el system, no se descarta."""
    extractor(ProjectMetadata(project_name="Portal de reservas"))
    session_id = _crear(cliente)

    cliente.post(f"/api/v1/sessions/{session_id}/estimate", data=CAMPOS, files={"description": (None, "Turno uno.")})
    cliente.post(f"/api/v1/sessions/{session_id}/estimate", data=CAMPOS, files={"description": (None, "Turno dos.")})

    assert "<project_metadata>" in generador.estimaciones[1]["system"]


def test_el_turno_se_envia_ya_renderizado_no_desnudo(cliente, generador) -> None:
    """El historial guarda el mensaje con sus vallas, para que sean homogéneas."""
    session_id = _crear(cliente)

    cliente.post(f"/api/v1/sessions/{session_id}/estimate", data=CAMPOS, files={"description": (None, "Turno uno.")})
    cliente.post(f"/api/v1/sessions/{session_id}/estimate", data=CAMPOS, files={"description": (None, "Turno dos.")})

    assert "<transcript_turn>" in generador.estimaciones[1]["messages"][0]["content"]


def test_un_fallo_del_proveedor_se_traduce_a_502(cliente, monkeypatch) -> None:
    def falla(*, system_prompt, messages, **kwargs):
        raise llm_service.LLMServiceError("503")

    monkeypatch.setattr(llm_service, "generate_turn", falla)
    session_id = _crear(cliente)

    respuesta = cliente.post(f"/api/v1/sessions/{session_id}/estimate", data=CAMPOS, files={"description": (None, "Hola.")})

    assert respuesta.status_code == 502
    # El turno fallido no debe quedar a medias en el historial.
    assert cliente.get(f"/api/v1/sessions/{session_id}").json()["message_count"] == 0


# --- Ventana deslizante ------------------------------------------------------


def test_la_ventana_deslizante_limita_los_turnos(cliente, generador) -> None:
    session_id = _crear(cliente)

    for indice in range(5):
        cliente.post(
            f"/api/v1/sessions/{session_id}/estimate",
            data=CAMPOS,
            files={"description": (None, f"Turno {indice}.")},
        )

    cuerpo = cliente.get(f"/api/v1/sessions/{session_id}").json()
    assert cuerpo["message_count"] == 6
    assert cuerpo["max_turns"] == 3


def test_al_ocho_turnos_el_array_enviado_no_crece(cliente, generador) -> None:
    """Requisito del enunciado: la ventana se respeta en lo que viaja al LLM."""
    session_id = _crear(cliente)

    for indice in range(8):
        cliente.post(
            f"/api/v1/sessions/{session_id}/estimate",
            data=CAMPOS,
            files={"description": (None, f"Turno {indice}.")},
        )

    assert max(len(c["messages"]) for c in generador.estimaciones) == 7


def test_el_historial_conserva_la_alternancia_de_roles(cliente, generador) -> None:
    session_id = _crear(cliente)

    for indice in range(5):
        cliente.post(
            f"/api/v1/sessions/{session_id}/estimate",
            data=CAMPOS,
            files={"description": (None, f"Turno {indice}.")},
        )

    for llamada in generador.estimaciones:
        roles = [m["role"] for m in llamada["messages"]]
        assert roles[0] == "user"


# --- Adjuntos ----------------------------------------------------------------


def _pdf(texto: str) -> bytes:
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
    offsets = []
    for numero, cuerpo in enumerate(objetos, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n" % numero + cuerpo + b"\nendobj\n"
    inicio = len(pdf)
    pdf += b"xref\n0 %d\n" % (len(objetos) + 1)
    pdf += b"0000000000 65535 f \n"
    for offset in offsets:
        pdf += b"%010d 00000 n \n" % offset
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objetos) + 1,
        inicio,
    )
    return bytes(pdf)


def test_un_adjunto_pdf_llega_al_prompt(cliente, generador) -> None:
    session_id = _crear(cliente)

    respuesta = cliente.post(
        f"/api/v1/sessions/{session_id}/estimate",
        data=CAMPOS,
        files={
            "description": (None, "Hablamos del portal."),
            "files": ("especificacion.pdf", _pdf("Trece milestones."), "application/pdf"),
        },
    )

    assert respuesta.status_code == 200
    enviado = generador.estimaciones[0]["messages"][0]["content"]
    assert "--- attachment: especificacion.pdf ---" in enviado
    assert "Trece milestones." in enviado


def test_un_tipo_no_soportado_devuelve_415(cliente, generador) -> None:
    session_id = _crear(cliente)

    respuesta = cliente.post(
        f"/api/v1/sessions/{session_id}/estimate",
        data=CAMPOS,
        files={
            "description": (None, "Hablamos."),
            "files": ("hoja.xlsx", b"contenido", "application/vnd.ms-excel"),
        },
    )

    assert respuesta.status_code == 415
    assert "hoja.xlsx" in respuesta.json()["detail"]


def test_un_pdf_corrupto_devuelve_422(cliente, generador) -> None:
    session_id = _crear(cliente)

    respuesta = cliente.post(
        f"/api/v1/sessions/{session_id}/estimate",
        data=CAMPOS,
        files={
            "description": (None, "Hablamos."),
            "files": ("roto.pdf", b"%PDF-1.4 no soy un pdf", "application/pdf"),
        },
    )

    assert respuesta.status_code == 422


def test_demasiados_adjuntos_devuelve_422(cliente, generador, monkeypatch) -> None:
    monkeypatch.setattr(sessions_router.config.settings, "max_attachments_per_request", 1)
    session_id = _crear(cliente)

    # Varios archivos exigen una lista plana de tuplas: httpx no acepta una lista
    # de archivos como valor de una clave, que es como se rompería el cliente.
    respuesta = cliente.post(
        f"/api/v1/sessions/{session_id}/estimate",
        data=CAMPOS,
        files=[
            ("description", (None, "Hablamos.")),
            ("files", ("a.pdf", _pdf("Uno."), "application/pdf")),
            ("files", ("b.pdf", _pdf("Dos."), "application/pdf")),
        ],
    )

    assert respuesta.status_code == 422


def test_un_adjunto_rechazado_no_consume_una_llamada(cliente, generador) -> None:
    session_id = _crear(cliente)

    cliente.post(
        f"/api/v1/sessions/{session_id}/estimate",
        data=CAMPOS,
        files={
            "description": (None, "Hablamos."),
            "files": ("hoja.xlsx", b"contenido", "application/vnd.ms-excel"),
        },
    )

    assert generador.llamadas == []


# --- Metadata en la respuesta -----------------------------------------------


def test_la_respuesta_incluye_la_metadata_actualizada(cliente, generador, extractor) -> None:
    extractor(ProjectMetadata(project_name="Portal de reservas", assumed_team_size=4))
    session_id = _crear(cliente)

    respuesta = cliente.post(f"/api/v1/sessions/{session_id}/estimate", data=CAMPOS, files={"description": (None, "Turno uno.")})

    metadata_cuerpo = respuesta.json()["metadata"]
    assert metadata_cuerpo["project_name"] == "Portal de reservas"
    assert metadata_cuerpo["assumed_team_size"] == 4


def test_la_metadata_se_consulta_despues_del_turno(cliente, generador, extractor) -> None:
    extractor(ProjectMetadata(project_name="Portal"))
    session_id = _crear(cliente)
    cliente.post(f"/api/v1/sessions/{session_id}/estimate", data=CAMPOS, files={"description": (None, "Turno uno.")})

    assert cliente.get(f"/api/v1/sessions/{session_id}").json()["metadata"]["project_name"] == "Portal"


# --- Validación de entrada ---------------------------------------------------


def test_falta_el_tipo_de_proyecto(cliente, generador) -> None:
    session_id = _crear(cliente)

    respuesta = cliente.post(f"/api/v1/sessions/{session_id}/estimate", data={"detail_level": "medium", "output_format": "phases_table"})

    assert respuesta.status_code == 422


def test_un_tipo_de_proyecto_invalido(cliente, generador) -> None:
    session_id = _crear(cliente)

    respuesta = cliente.post(f"/api/v1/sessions/{session_id}/estimate", data={**CAMPOS, "project_type": "no_existe"})

    assert respuesta.status_code == 422


def test_falta_la_descripcion(cliente, generador) -> None:
    session_id = _crear(cliente)

    respuesta = cliente.post(f"/api/v1/sessions/{session_id}/estimate", data=CAMPOS)

    assert respuesta.status_code == 422