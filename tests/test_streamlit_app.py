"""Pruebas de la interfaz Streamlit sin arrancar un servidor HTTP."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

import httpx


class RespuestaFalsa:
    """Respuesta HTTP mínima para comprobar el envío desde el formulario."""

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {
            "text": "## Estimación\n\n40 horas",
            "prompt_version": "v1",
            "model": "gpt-4o-mini",
            "provider": "openai",
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }


def test_el_formulario_envia_la_solicitud_al_api(monkeypatch) -> None:
    llamada: dict[str, object] = {}

    def post_falso(url: str, **kwargs: object) -> RespuestaFalsa:
        llamada["url"] = url
        llamada.update(kwargs)
        return RespuestaFalsa()

    monkeypatch.setattr(httpx, "post", post_falso)
    app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
    app = AppTest.from_file(app_path).run()

    app.text_area(key="estimation_description").set_value(
        "Una aplicación web para organizar reservas y pagos de una academia."
    )
    app.button[0].click().run()

    assert not app.exception
    assert llamada["url"].endswith("/api/v1/estimate")
    assert llamada["json"] == {
        "description": "Una aplicación web para organizar reservas y pagos de una academia.",
        "project_type": "mobile_app",
        "detail_level": "summary",
        "output_format": "phases_table",
    }
    assert any("40 horas" in markdown.value for markdown in app.markdown)


DESCRIPCION_VALIDA = "Una aplicación web para organizar reservas y pagos de una academia."


def _app_con_envio(monkeypatch, post_falso) -> AppTest:
    """Arranca la interfaz con `httpx.post` sustituido y la descripción puesta."""
    monkeypatch.setattr(httpx, "post", post_falso)
    app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
    app = AppTest.from_file(app_path).run()
    app.text_area(key="estimation_description").set_value(DESCRIPCION_VALIDA)
    return app


def test_una_descripcion_insuficiente_no_llega_al_api(monkeypatch) -> None:
    """El mínimo de 20 caracteres se valida en el cliente, sin gastar llamada."""

    def post_falso(url: str, **kwargs: object) -> RespuestaFalsa:
        raise AssertionError("no debe llamar al API con una descripción demasiado corta")

    monkeypatch.setattr(httpx, "post", post_falso)
    app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
    app = AppTest.from_file(app_path).run()
    app.text_area(key="estimation_description").set_value("app pequeña")
    app.button[0].click().run()

    assert not app.exception
    assert any("al menos 20 caracteres" in error.value for error in app.error)


def test_un_fallo_http_se_muestra_como_error_de_conexion(monkeypatch) -> None:
    """Un `httpx.HTTPError` produce un mensaje accionable, no una excepción."""

    def post_falso(url: str, **kwargs: object) -> RespuestaFalsa:
        raise httpx.ConnectError("connection refused")

    app = _app_con_envio(monkeypatch, post_falso)
    app.button[0].click().run()

    assert not app.exception
    assert any("No se pudo obtener la estimación" in error.value for error in app.error)


def test_un_fallo_de_proveedor_no_expone_el_detalle_interno(monkeypatch) -> None:
    """El 502 del backend se muestra igual que cualquier otro fallo HTTP."""

    def post_falso(url: str, **kwargs: object) -> RespuestaFalsa:
        raise httpx.HTTPStatusError(
            "502 Server Error: El proveedor LLM no pudo generar la estimación.",
            request=httpx.Request("POST", url),
            response=httpx.Response(502),
        )

    app = _app_con_envio(monkeypatch, post_falso)
    app.button[0].click().run()

    assert not app.exception
    assert any("No se pudo obtener la estimación" in error.value for error in app.error)
