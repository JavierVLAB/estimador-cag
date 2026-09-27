"""Pruebas del endpoint de estimación con un proveedor LLM local falso."""

import pytest
from pydantic import ValidationError

from app.schemas.estimation import (
    DetailLevel,
    EstimationRequest,
    EstimationResponse,
    OutputFormat,
    ProjectType,
    TokenUsage,
)
from app.services import llm_service

ESTIMACION_FALSA = "## Estimación: Landing page\n\n**Total estimado: 40 horas**"
BODY_VALIDO = {
    "description": "Una landing page con formulario e integración con CRM.",
    "project_type": "web_saas",
    "detail_level": "medium",
    "output_format": "phases_table",
}


def test_los_contratos_usan_2000_caracteres_y_el_campo_texto() -> None:
    request = EstimationRequest(
        description="a" * 2_000,
        project_type=ProjectType.WEB_SAAS,
        detail_level=DetailLevel.MEDIUM,
        output_format=OutputFormat.PHASES_TABLE,
    )
    response = EstimationResponse(
        text=ESTIMACION_FALSA,
        prompt_version="v1",
        model="gpt-4o-mini",
        provider="openai",
        usage=TokenUsage(input_tokens=22, output_tokens=18, total_tokens=40),
    )

    assert request.description == "a" * 2_000
    assert response.model_dump() == {
        "text": ESTIMACION_FALSA,
        "prompt_version": "v1",
        "model": "gpt-4o-mini",
        "provider": "openai",
        "usage": {"input_tokens": 22, "output_tokens": 18, "total_tokens": 40},
    }
    with pytest.raises(ValidationError):
        EstimationRequest(
            description="a" * 2_001,
            project_type=ProjectType.WEB_SAAS,
            detail_level=DetailLevel.MEDIUM,
            output_format=OutputFormat.PHASES_TABLE,
        )


@pytest.fixture
def sin_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sustituye la llamada al proveedor por una respuesta fija."""

    def _fake(request: EstimationRequest) -> llm_service.EstimationResult:
        assert request.description == BODY_VALIDO["description"]
        return llm_service.EstimationResult(
            estimation=ESTIMACION_FALSA,
            model="gpt-4o-mini",
            provider="openai",
            usage=llm_service.TokenUsage(
                input_tokens=22,
                output_tokens=18,
                total_tokens=40,
            ),
        )

    monkeypatch.setattr(llm_service, "generate_estimation", _fake)


def test_health_responde_ok(client) -> None:
    respuesta = client.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "ok"


def test_estimacion_correcta_incluye_version_de_prompt(client, sin_llm) -> None:
    respuesta = client.post("/api/v1/estimate", json=BODY_VALIDO)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo == {
        "text": ESTIMACION_FALSA,
        "prompt_version": "v1",
        "model": "gpt-4o-mini",
        "provider": "openai",
        "usage": {
            "input_tokens": 22,
            "output_tokens": 18,
            "total_tokens": 40,
        },
    }


@pytest.mark.parametrize("campo_ausente", BODY_VALIDO)
def test_un_campo_obligatorio_ausente_devuelve_422(
    client, monkeypatch: pytest.MonkeyPatch, campo_ausente: str
) -> None:
    def _no_llamar(_: EstimationRequest):
        raise AssertionError("No se debe llamar al LLM con una petición inválida")

    monkeypatch.setattr(llm_service, "generate_estimation", _no_llamar)
    body = {key: value for key, value in BODY_VALIDO.items() if key != campo_ausente}

    respuesta = client.post("/api/v1/estimate", json=body)

    assert respuesta.status_code == 422


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project_type", "desktop_app"),
        ("detail_level", "exhaustive"),
        ("output_format", "json"),
    ],
)
def test_una_opcion_invalida_devuelve_422(
    client, monkeypatch: pytest.MonkeyPatch, field: str, value: str
) -> None:
    def _no_llamar(_: EstimationRequest):
        raise AssertionError("No se debe llamar al LLM con una petición inválida")

    monkeypatch.setattr(llm_service, "generate_estimation", _no_llamar)
    body = {**BODY_VALIDO, field: value}

    respuesta = client.post("/api/v1/estimate", json=body)

    assert respuesta.status_code == 422


def test_descripcion_corta_devuelve_422(client, monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_llamar(_: EstimationRequest):
        raise AssertionError("No se debe llamar al LLM con una petición inválida")

    monkeypatch.setattr(llm_service, "generate_estimation", _no_llamar)

    respuesta = client.post(
        "/api/v1/estimate", json={**BODY_VALIDO, "description": "  demasiado corta  "}
    )

    assert respuesta.status_code == 422


def test_fallo_del_proveedor_devuelve_502(client, monkeypatch: pytest.MonkeyPatch) -> None:
    def _falla(_: EstimationRequest):
        raise llm_service.LLMServiceError("detalle-interno-que-no-debe-filtrarse")

    monkeypatch.setattr(llm_service, "generate_estimation", _falla)

    respuesta = client.post("/api/v1/estimate", json=BODY_VALIDO)

    assert respuesta.status_code == 502
    assert "detalle-interno-que-no-debe-filtrarse" not in respuesta.text


def test_error_propio_se_reporta_como_500(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _bug(_: EstimationRequest):
        raise KeyError("campo_interno")

    monkeypatch.setattr(llm_service, "generate_estimation", _bug)

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as cliente_sin_raise:
        respuesta = cliente_sin_raise.post("/api/v1/estimate", json=BODY_VALIDO)

    assert respuesta.status_code == 500
    assert "campo_interno" not in respuesta.text


def test_descripcion_demasiado_larga_devuelve_422(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _no_llamar(_: EstimationRequest):
        raise AssertionError("No se debe llamar al LLM con una entrada inválida")

    monkeypatch.setattr(llm_service, "generate_estimation", _no_llamar)

    respuesta = client.post(
        "/api/v1/estimate", json={**BODY_VALIDO, "description": "a" * 2_001}
    )

    assert respuesta.status_code == 422
