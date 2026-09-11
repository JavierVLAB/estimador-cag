"""Tests del endpoint de estimación, con el proveedor LLM sustituido."""

import pytest

from app.services import llm_service

ESTIMACION_FALSA = "## Estimación: Landing page\n\n**Total estimado: 40 horas**"


@pytest.fixture
def sin_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sustituye la llamada al proveedor por una respuesta fija."""

    def _fake(transcription: str) -> llm_service.EstimationResult:
        return llm_service.EstimationResult(
            estimation=ESTIMACION_FALSA,
            model="gpt-4o-mini",
            provider="openai",
        )

    monkeypatch.setattr(llm_service, "generate_estimation", _fake)


def test_health_responde_ok(client) -> None:
    respuesta = client.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "ok"


def test_estimacion_correcta(client, sin_llm) -> None:
    respuesta = client.post(
        "/api/v1/estimate",
        json={"transcription": "El cliente quiere una landing page con formulario."},
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estimation"] == ESTIMACION_FALSA
    assert cuerpo["model"] == "gpt-4o-mini"
    assert cuerpo["provider"] == "openai"


def test_transcripcion_ausente(client, monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_llamar(transcription: str):
        raise AssertionError("No se debe llamar al LLM con una petición inválida")

    monkeypatch.setattr(llm_service, "generate_estimation", _no_llamar)

    respuesta = client.post("/api/v1/estimate", json={})

    assert respuesta.status_code == 422


def test_transcripcion_en_blanco(client, monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_llamar(transcription: str):
        raise AssertionError("No se debe llamar al LLM con una transcripción vacía")

    monkeypatch.setattr(llm_service, "generate_estimation", _no_llamar)

    respuesta = client.post("/api/v1/estimate", json={"transcription": "   "})

    assert respuesta.status_code == 422


def test_fallo_del_proveedor_devuelve_502(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _falla(transcription: str):
        raise RuntimeError("detalle-interno-que-no-debe-filtrarse")

    monkeypatch.setattr(llm_service, "generate_estimation", _falla)

    respuesta = client.post(
        "/api/v1/estimate", json={"transcription": "Una transcripción cualquiera."}
    )

    assert respuesta.status_code == 502
    assert "detalle-interno-que-no-debe-filtrarse" not in respuesta.text
