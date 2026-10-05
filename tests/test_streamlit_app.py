"""Pruebas de la interfaz Streamlit sin arrancar un servidor HTTP.

`httpx.post` se sustituye siempre, así que ningún test toca la red. Como la
interfaz abre una sesión al cargar, el doble tiene que responder también a esa
primera llamada.
"""

from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

DESCRIPCION_VALIDA = "Una aplicación web para organizar reservas y pagos de una academia."
APP_PATH = Path(__file__).resolve().parents[1] / "streamlit_app.py"

CUERPO_ESTIMACION = {
    "text": "## Estimación\n\n40 horas",
    "prompt_version": "v3",
    "model": "gpt-4o-mini",
    "provider": "openai",
    "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    "metadata": {"project_name": "Portal de reservas"},
    "turns_kept": 1,
}


class RespuestaFalsa:
    """Respuesta HTTP mínima para comprobar el envío desde el formulario."""

    def __init__(self, status_code: int = 200, cuerpo: dict | None = None) -> None:
        self.status_code = status_code
        self._cuerpo = CUERPO_ESTIMACION if cuerpo is None else cuerpo

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{self.status_code}",
                request=httpx.Request("POST", "http://x"),
                response=httpx.Response(self.status_code),
            )

    def json(self) -> dict:
        return self._cuerpo


class ClienteFalso:
    """Sustituto de `httpx.post` que registra las llamadas y responde por ruta.

    Un patrón puede asociar una lista de respuestas, que se van consumiendo en
    orden; la última se repite. Hace falta para el 404 followed de un reintento,
    donde la primera llamada al turno falla y la segunda tiene que funcionar.
    """

    def __init__(self, respuestas: dict[str, object] | None = None) -> None:
        self.llamadas: list[dict] = []
        self.respuestas = respuestas or {}

    def __call__(self, url: str, **kwargs: object) -> RespuestaFalsa:
        self.llamadas.append({"url": url, **kwargs})
        for patron, respuesta in self.respuestas.items():
            if patron not in url:
                continue
            if isinstance(respuesta, list):
                previas = [
                    c for c in self.llamadas[:-1] if patron in c["url"]
                ]
                return respuesta[min(len(previas), len(respuesta) - 1)]
            return respuesta
        if url.rstrip("/").endswith("/sessions"):
            return RespuestaFalsa(201, {"session_id": "sesion-de-prueba"})
        return RespuestaFalsa()


@pytest.fixture
def cliente(monkeypatch: pytest.MonkeyPatch) -> ClienteFalso:
    falso = ClienteFalso()
    monkeypatch.setattr(httpx, "post", falso)
    return falso


def _enviar(app: AppTest, descripcion: str = DESCRIPCION_VALIDA) -> AppTest:
    app.text_area[0].set_value(descripcion)
    return app.button[0].click().run()


# --- Apertura de sesión ------------------------------------------------------


def test_al_cargar_se_abre_una_sesion(cliente) -> None:
    AppTest.from_file(APP_PATH).run()

    assert cliente.llamadas[0]["url"].endswith("/api/v1/sessions")


def test_el_identificador_de_sesion_se_conserva_entre_turnos(cliente) -> None:
    app = AppTest.from_file(APP_PATH).run()
    app = _enviar(app)

    # El segundo turno debe ir a la sesión ya abierta, sin volver a crearla.
    turn_urls = [c["url"] for c in cliente.llamadas if "/estimate" in c["url"]]
    assert turn_urls[0].endswith("/sessions/sesion-de-prueba/estimate")

    app = _enviar(app)
    turn_urls = [c["url"] for c in cliente.llamadas if "/estimate" in c["url"]]
    assert len(turn_urls) == 2
    assert all("/sessions/sesion-de-prueba/estimate" in url for url in turn_urls)


# --- Envío del turno ---------------------------------------------------------


def test_el_turno_se_envia_al_endpoint_de_sesion(cliente) -> None:
    app = AppTest.from_file(APP_PATH).run()

    app = _enviar(app)

    assert not app.exception
    envio = [c for c in cliente.llamadas if "/estimate" in c["url"]][0]
    assert envio["data"] == {
        "description": DESCRIPCION_VALIDA,
        "project_type": "mobile_app",
        "detail_level": "summary",
        "output_format": "phases_table",
    }


def test_la_caja_de_texto_se_vacia_tras_enviar(cliente) -> None:
    """Sin esto, el texto se queda e invita a reenviar el mismo turno."""
    app = AppTest.from_file(APP_PATH).run()
    app = _enviar(app)

    assert app.text_area[0].value == ""


def test_los_adjuntos_no_se_arrastran_al_siguiente_turno(cliente) -> None:
    app = AppTest.from_file(APP_PATH).run()
    app.file_uploader[0].upload("notas.pdf", b"%PDF-1.4\nfake\n", "application/pdf")
    app = _enviar(app)

    assert app.file_uploader[0].value == []


def test_los_selectores_se_recuerdan_entre_turnos(cliente) -> None:
    """Contrapartida: limpiar el texto no debe borrar lo que sí conviene mantener."""
    app = AppTest.from_file(APP_PATH).run()
    app.selectbox(key="estimation_output_format").select("narrative")
    app = _enviar(app)

    assert app.selectbox(key="estimation_output_format").value == "narrative"


def test_la_estimacion_se_muestra(cliente) -> None:
    app = _enviar(AppTest.from_file(APP_PATH).run())

    assert any("40 horas" in markdown.value for markdown in app.markdown)


def test_un_adjunto_se_envia_como_multipart(cliente) -> None:
    """Con adjuntos el envío pasa a multipart, que es lo que el endpoint exige."""
    app = AppTest.from_file(APP_PATH).run()

    app.file_uploader[0].upload("especificacion.pdf", b"%PDF-1.4 contenido", "application/pdf")
    app = _enviar(app)

    assert not app.exception
    envio = [c for c in cliente.llamadas if "/estimate" in c["url"]][0]
    assert "files" in envio
    assert envio["files"][0][0] == "files"
    assert envio["files"][0][1][0] == "especificacion.pdf"


# --- Panel de contexto -------------------------------------------------------


def test_sin_turnos_el_panel_dice_que_no_hay_datos(cliente) -> None:
    app = AppTest.from_file(APP_PATH).run()

    assert any("Todavía no hay datos del proyecto" in c.value for c in app.caption)


def test_el_panel_muestra_la_metadata_del_turno(cliente) -> None:
    app = _enviar(AppTest.from_file(APP_PATH).run())

    assert any("Portal de reservas" in c.value for c in app.caption)


def test_el_panel_muestra_los_turnos_conservados(cliente) -> None:
    app = _enviar(AppTest.from_file(APP_PATH).run())

    assert any("Turnos conservados" in c.value for c in app.caption)


def test_una_metadata_vacia_no_rompe_el_panel(cliente) -> None:
    """Metadata vacía es un estado legítimo, no un fallo que mostrar como error."""
    cliente.respuestas["/estimate"] = RespuestaFalsa(
        200, {**CUERPO_ESTIMACION, "metadata": {}}
    )

    app = _enviar(AppTest.from_file(APP_PATH).run())

    assert not app.exception
    assert any("Todavía no hay datos del proyecto" in c.value for c in app.caption)


# --- Nueva conversación ------------------------------------------------------


def test_nueva_conversacion_abra_otra_sesion(cliente) -> None:
    app = _enviar(AppTest.from_file(APP_PATH).run())

    app.button[2].click().run()

    assert any(
        c["url"].endswith("/api/v1/sessions") for c in cliente.llamadas
    )
    assert app.session_state["turns_kept"] == 0


def test_nueva_conversacion_limpia_el_resultado(cliente) -> None:
    app = _enviar(AppTest.from_file(APP_PATH).run())
    assert any("40 horas" in markdown.value for markdown in app.markdown)

    app.button[2].click().run()

    assert not any("40 horas" in markdown.value for markdown in app.markdown)


# --- Recuperación de sesión perdida -----------------------------------------


def test_un_404_abre_una_sesion_nueva_y_reintenta(cliente) -> None:
    """El backend puede haberse reiniciado: el turno no debe perderse."""
    cliente.respuestas["/estimate"] = [
        RespuestaFalsa(404, {"detail": "No existe la sesión."}),
        RespuestaFalsa(200, CUERPO_ESTIMACION),
    ]

    app = _enviar(AppTest.from_file(APP_PATH).run())

    assert not app.exception
    assert any("40 horas" in markdown.value for markdown in app.markdown)
    # Sesión nueva abierta tras el 404, y el turno enviado a ella.
    assert len([c for c in cliente.llamadas if c["url"].endswith("/sessions")]) == 2


def test_un_404_que_no_se_puede_recuperar_avisa(cliente, monkeypatch) -> None:
    cliente.respuestas["/sessions"] = RespuestaFalsa(500, {"detail": "error"})
    monkeypatch.setattr(
        httpx, "post", ClienteFalso({"/estimate": RespuestaFalsa(404, {})})
    )

    app = _enviar(AppTest.from_file(APP_PATH).run())

    assert not app.exception
    assert any("No se pudo obtener la estimación" in e.value for e in app.error)


# --- Validación y fallos -----------------------------------------------------


def test_una_descripcion_insuficiente_no_llega_al_api(cliente) -> None:
    """El mínimo de 20 caracteres se valida en el cliente, sin gastar llamada."""

    def post_falso(url: str, **kwargs: object) -> RespuestaFalsa:
        raise AssertionError("no debe llamar al API con una descripción demasiado corta")

    cliente.llamadas.clear()
    app = AppTest.from_file(APP_PATH).run()
    app.text_area[0].set_value("app pequeña")
    app.button[0].click().run()

    assert not app.exception
    assert any("al menos 20 caracteres" in error.value for error in app.error)
    assert not [c for c in cliente.llamadas if "/estimate" in c["url"]]


def test_un_fallo_http_se_muestra_como_error_de_conexion(monkeypatch) -> None:
    def post_falso(url: str, **kwargs: object) -> RespuestaFalsa:
        if "/estimate" in url:
            raise httpx.ConnectError("connection refused")
        return ClienteFalso()(url, **kwargs)

    monkeypatch.setattr(httpx, "post", post_falso)
    app = AppTest.from_file(APP_PATH).run()
    app.text_area[0].set_value(DESCRIPCION_VALIDA)
    app.button[0].click().run()

    assert not app.exception
    assert any("No se pudo obtener la estimación" in error.value for error in app.error)


def test_un_fallo_de_proveedor_no_expone_el_detalle_interno(monkeypatch) -> None:
    """El 502 del backend se muestra igual que cualquier otro fallo HTTP."""

    def post_falso(url: str, **kwargs: object) -> RespuestaFalsa:
        if "/estimate" in url:
            raise httpx.HTTPStatusError(
                "502 Server Error: El proveedor LLM no pudo generar la estimación.",
                request=httpx.Request("POST", url),
                response=httpx.Response(502),
            )
        return ClienteFalso()(url, **kwargs)

    monkeypatch.setattr(httpx, "post", post_falso)
    app = AppTest.from_file(APP_PATH).run()
    app.text_area[0].set_value(DESCRIPCION_VALIDA)
    app.button[0].click().run()

    assert not app.exception
    assert any("No se pudo obtener la estimación" in error.value for error in app.error)


def test_un_backend_caido_no_rompe_la_pantalla(cliente, monkeypatch) -> None:
    """Sin sesión no se puede estimar, pero la interfaz debe explicar el motivo."""
    monkeypatch.setattr(httpx, "post", ClienteFalso({"/sessions": RespuestaFalsa(500, {})}))

    app = AppTest.from_file(APP_PATH).run()

    assert not app.exception
    assert any("No se pudo abrir una sesión" in w.value for w in app.warning)