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
