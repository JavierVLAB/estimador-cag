"""Los tres escenarios que pide el enunciado, de extremo a extremo.

Aquí no hay dobles: el backend real, con el proveedor sustituido. Los tres
comportamientos que el enunciado quiere ver dependen de cómo se encadenan
router, historial, metadata y adjuntos, y un doble por pieza los comprobaría por
separado sin demostrar que juntos funcionan.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import sessions as sessions_router
from app.services import llm_service, metadata

CAMPOS = {
    "project_type": "web_saas",
    "detail_level": "medium",
    "output_format": "phases_table",
}

BASE = "/api/v1"


def _pdf(texto: str) -> bytes:
    """PDF mínimo de una página, construido a mano para no añadir dependencias."""
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


class _GeneradorQueRegistra:
    """Proveedor falso que guarda todo lo que recibe y responde con texto fijo."""

    def __init__(self) -> None:
        self.llamadas: list[dict] = []

    def generar(self, *, system_prompt: str, messages: list[dict], **kwargs):
        es_extraccion = "max_output_tokens" in kwargs
        self.llamadas.append(
            {
                "system": system_prompt,
                "messages": [dict(m) for m in messages],
                "extraccion": es_extraccion,
            }
        )
        if es_extraccion:
            texto = (
                '{"project_name": "Portal de reservas", "assumed_team_size": 4, '
                '"mentioned_technologies": ["React"], "agreed_scope": "Solo el motor '
                'de disponibilidad"}'
            )
        else:
            texto = "## Estimación\n\n320 horas, equipo de 4 personas."
        return llm_service.CompletionResult(
            text=texto,
            model="gpt-4o-mini",
            provider="openai",
            usage=llm_service.TokenUsage(
                input_tokens=120, output_tokens=40, total_tokens=160
            ),
        )

    @property
    def estimaciones(self) -> list[dict]:
        return [c for c in self.llamadas if not c["extraccion"]]


@pytest.fixture
def generador(monkeypatch: pytest.MonkeyPatch) -> _GeneradorQueRegistra:
    falso = _GeneradorQueRegistra()
    monkeypatch.setattr(llm_service, "generate_turn", falso.generar)
    return falso


@pytest.fixture
def cliente() -> TestClient:
    sessions_router._store.clear()
    # Tres turnos para que los números esperados sean legibles; el límite real
    # vive en la configuración y se comprueba aparte.
    sessions_router._store._max_turns = 3
    return TestClient(app)


def _turno(cliente: TestClient, session_id: str, texto: str, archivos=None) -> dict:
    """Envía un turno y falla el test con el detalle si algo va mal."""
    archivos = archivos or {}
    respuesta = cliente.post(
        f"{BASE}/sessions/{session_id}/estimate",
        data=CAMPOS,
        files={"description": (None, texto), **archivos},
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


# --- Escenario 1: la metadata se actualiza entre peticiones -------------------


def test_el_primer_turno_extrae_la_metadata(cliente, generador) -> None:
    """La extracción ocurre ya en el turno 1: no hace falta un segundo turno."""
    session_id = cliente.post(f"{BASE}/sessions").json()["session_id"]

    cuerpo = _turno(cliente, session_id, "Queremos un portal de reservas.")

    assert cuerpo["metadata"]["project_name"] == "Portal de reservas"
    assert cuerpo["metadata"]["mentioned_technologies"] == ["React"]


def test_la_metadata_del_turno_anterior_llega_al_siguiente(cliente, generador) -> None:
    session_id = cliente.post(f"{BASE}/sessions").json()["session_id"]
    _turno(cliente, session_id, "Se llamará Portal de reservas, con 4 personas.")

    _turno(cliente, session_id, "Vale. Ahora queremos añadir pagos.")

    segundo_system = generador.estimaciones[1]["system"]
    assert "<project_metadata>" in segundo_system
    assert "Portal de reservas" in segundo_system
    assert "4 personas" in segundo_system


def test_los_datos_no_se_pierden_entre_turnos(cliente, generador) -> None:
    session_id = cliente.post(f"{BASE}/sessions").json()["session_id"]
    _turno(cliente, session_id, "Se llamará Portal de reservas, con 4 personas.")
    cuerpo = _turno(cliente, session_id, "Vale.")

    assert cuerpo["metadata"]["project_name"] == "Portal de reservas"
    assert cuerpo["metadata"]["assumed_team_size"] == 4


# --- Escenario 2: un adjunto cambia la estimación ----------------------------


def test_el_adjunto_llega_al_prompt_del_turno(cliente, generador) -> None:
    session_id = cliente.post(f"{BASE}/sessions").json()["session_id"]

    _turno(
        cliente,
        session_id,
        "Hablamos del portal.",
        archivos={"files": ("ficha.pdf", _pdf("Dieciseis milestones."), "application/pdf")},
    )

    enviado = generador.estimaciones[0]["messages"][0]["content"]
    assert "--- attachment: ficha.pdf ---" in enviado
    assert "Dieciseis milestones." in enviado


def test_sin_adjunto_el_turno_no_lleva_vallas(cliente, generador) -> None:
    session_id = cliente.post(f"{BASE}/sessions").json()["session_id"]

    _turno(cliente, session_id, "Hablamos del portal.")

    enviado = generador.estimaciones[0]["messages"][0]["content"]
    # La plantilla menciona la valla en sus instrucciones, así que el criterio es
    # que no haya ningún bloque cerrado, no que no aparezca la palabra.
    assert "--- end attachment ---" not in enviado


def test_el_adjunto_no_contamina_el_siguiente_turno(cliente, generador) -> None:
    session_id = cliente.post(f"{BASE}/sessions").json()["session_id"]
    _turno(
        cliente,
        session_id,
        "Primera reunión.",
        archivos={"files": ("ficha.pdf", _pdf("Dieciseis milestones."), "application/pdf")},
    )

    _turno(cliente, session_id, "Segunda reunión, sin material nuevo.")

    # En el segundo turno `messages` es [user_1, assistant_1, user_2].
    anterior = generador.estimaciones[1]["messages"][0]["content"]
    nuevo = generador.estimaciones[1]["messages"][2]["content"]
    assert "Dieciseis milestones." in anterior  # el historial sí lo conserva
    assert "--- end attachment ---" not in nuevo  # y el turno nuevo no inventa vallas


# --- Escenario 3: ocho turnos sin crecer el array enviado --------------------


def test_ocho_turnos_no_hacen_crecer_el_array_de_mensajes(cliente, generador) -> None:
    session_id = cliente.post(f"{BASE}/sessions").json()["session_id"]

    for indice in range(8):
        _turno(cliente, session_id, f"Reunión número {indice}.")

    longitudes = [len(c["messages"]) for c in generador.estimaciones]
    # Crece hasta el límite y ahí se queda: 3 turnos previos + el actual.
    assert longitudes[0] == 1
    assert longitudes == [1, 3, 5, 7, 7, 7, 7, 7]


def test_el_limite_aplicado_es_el_de_la_configuracion(cliente, generador) -> None:
    session_id = cliente.post(f"{BASE}/sessions").json()["session_id"]

    for indice in range(8):
        _turno(cliente, session_id, f"Reunión {indice}.")

    cuerpo = cliente.get(f"{BASE}/sessions/{session_id}").json()
    assert cuerpo["max_turns"] == sessions_router._store.max_turns
    assert cuerpo["message_count"] == sessions_router._store.max_turns * 2


def test_el_historial_recortado_sigue_alternando_turnos(cliente, generador) -> None:
    session_id = cliente.post(f"{BASE}/sessions").json()["session_id"]

    for indice in range(8):
        _turno(cliente, session_id, f"Reunión {indice}.")

    for llamada in generador.estimaciones:
        roles = [m["role"] for m in llamada["messages"]]
        # El primer turno envía un único mensaje de usuario; a partir de ahí la
        # lista son pares. Lo que no puede pasar es una desalternancia.
        assert roles[0] == "user"
        assert all(
            rol == ("user" if indice % 2 == 0 else "assistant")
            for indice, rol in enumerate(roles)
        )


def test_lo_recortado_no_desaparece_de_la_metadata(cliente, generador) -> None:
    """La ventana borra turnos, no hechos: la metadata sobrevive a los dos."""
    session_id = cliente.post(f"{BASE}/sessions").json()["session_id"]
    _turno(cliente, session_id, "Se llamará Portal de reservas.")

    for indice in range(7):
        cuerpo = _turno(cliente, session_id, f"Reunión {indice}.")

    assert cuerpo["metadata"]["project_name"] == "Portal de reservas"
    assert "Portal de reservas" in generador.estimaciones[-1]["system"]