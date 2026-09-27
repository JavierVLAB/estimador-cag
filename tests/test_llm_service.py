"""Pruebas de generación normal con SDKs locales sustituidos por dobles."""

import logging
import types

import pytest

from app import config
from app.schemas.estimation import (
    DetailLevel,
    EstimationRequest,
    OutputFormat,
    ProjectType,
)
from app.services import llm_service
from app.services.llm_service import LLMServiceError


REQUEST = EstimationRequest(
    description="El cliente quiere una landing page con formulario de contacto.",
    project_type=ProjectType.WEB_SAAS,
    detail_level=DetailLevel.MEDIUM,
    output_format=OutputFormat.PHASES_TABLE,
)


@pytest.fixture
def settings_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_service.config, "settings", _settings("openai"))


@pytest.fixture
def settings_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_service.config, "settings", _settings("anthropic"))


def _settings(provider: str, prompt_version: str = "v1") -> config.Settings:
    return config.Settings(
        _env_file=None,
        llm_provider=provider,
        llm_prompt_version=prompt_version,
        llm_timeout_seconds=12.5,
        llm_max_retries=3,
        llm_max_output_tokens=100,
        openai_api_key=None,
        anthropic_api_key=None,
    )


def _respuesta_openai(
    *,
    finish_reason: str = "stop",
    content: str = "## Estimación: **40 h**",
    usage: types.SimpleNamespace | None = None,
) -> types.SimpleNamespace:
    usage = usage or types.SimpleNamespace(
        prompt_tokens=11, completion_tokens=9, total_tokens=20
    )
    return types.SimpleNamespace(
        usage=usage,
        choices=[
            types.SimpleNamespace(
                finish_reason=finish_reason,
                message=types.SimpleNamespace(content=content),
            )
        ],
    )


def _respuesta_anthropic(
    *,
    stop_reason: str = "end_turn",
    bloques: list | None = None,
    usage: types.SimpleNamespace | None = None,
) -> types.SimpleNamespace:
    bloques = bloques or [types.SimpleNamespace(type="text", text="## Estimación")]
    usage = usage or types.SimpleNamespace(input_tokens=9, output_tokens=5)
    return types.SimpleNamespace(stop_reason=stop_reason, content=bloques, usage=usage)


def test_cliente_openai_recibe_timeout_retries_y_max_tokens(
    monkeypatch: pytest.MonkeyPatch, settings_openai
) -> None:
    constructor_kwargs: dict = {}
    create_kwargs: dict = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            constructor_kwargs.update(kwargs)

        @property
        def chat(self):
            class FakeCompletions:
                def create(self, **kwargs):
                    create_kwargs.update(kwargs)
                    return _respuesta_openai()

            return types.SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)

    resultado = llm_service.generate_estimation(REQUEST)

    assert constructor_kwargs["timeout"] == 12.5
    assert constructor_kwargs["max_retries"] == 3
    assert create_kwargs["max_tokens"] == 100
    assert resultado.estimation == "## Estimación: **40 h**"


def test_openai_recibe_system_y_user_renderizados_por_separado(
    monkeypatch: pytest.MonkeyPatch, settings_openai
) -> None:
    llamada: dict = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            pass

        @property
        def chat(self):
            class FakeCompletions:
                def create(self, **kwargs):
                    llamada.update(kwargs)
                    return _respuesta_openai()

            return types.SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)

    llm_service.generate_estimation(REQUEST)

    assert llamada["messages"][0]["role"] == "system"
    assert llamada["messages"][1]["role"] == "user"
    assert REQUEST.description not in llamada["messages"][0]["content"]
    assert (
        f"<project_description>\n{REQUEST.description}\n</project_description>"
        in llamada["messages"][1]["content"]
    )


def test_v2_se_selecciona_desde_la_configuracion_del_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llamada: dict = {}
    monkeypatch.setattr(llm_service.config, "settings", _settings("openai", "v2"))

    class FakeOpenAI:
        def __init__(self, **kwargs):
            pass

        @property
        def chat(self):
            class FakeCompletions:
                def create(self, **kwargs):
                    llamada.update(kwargs)
                    return _respuesta_openai()

            return types.SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)

    resultado = llm_service.generate_estimation(REQUEST)

    assert resultado.prompt_version == "v2"
    assert "supuestos verificables" in llamada["messages"][0]["content"]
    assert REQUEST.description not in llamada["messages"][0]["content"]
    assert REQUEST.description in llamada["messages"][1]["content"]


def test_el_registro_del_prompt_no_expone_su_contenido(
    monkeypatch: pytest.MonkeyPatch,
    settings_openai,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger=llm_service.__name__)

    class FakeOpenAI:
        def __init__(self, **kwargs):
            pass

        @property
        def chat(self):
            class FakeCompletions:
                def create(self, **kwargs):
                    return _respuesta_openai()

            return types.SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)

    llm_service.generate_estimation(REQUEST)

    record = next(
        record
        for record in caplog.records
        if record.message.startswith("Prompt de estimación preparado:")
    )
    assert record.prompt_version == "v1"
    assert record.llm_provider == "openai"
    assert record.llm_model == "gpt-4o-mini"
    assert len(record.prompt_sha256) == 64
    assert record.system_prompt_characters > 0
    assert record.user_prompt_characters > 0
    assert record.prompt_characters == (
        record.system_prompt_characters + record.user_prompt_characters
    )
    assert "version=v1 provider=openai model=gpt-4o-mini" in caplog.text
    assert f"sha256={record.prompt_sha256}" in caplog.text
    assert f"system_chars={record.system_prompt_characters}" in caplog.text
    assert f"user_chars={record.user_prompt_characters}" in caplog.text
    assert f"total_chars={record.prompt_characters}" in caplog.text
    assert REQUEST.description not in caplog.text
    assert "Eres una persona experta" not in caplog.text


def test_anthropic_recibe_system_y_user_renderizados_por_separado(
    monkeypatch: pytest.MonkeyPatch, settings_anthropic
) -> None:
    llamada: dict = {}

    class FakeAnthropic:
        def __init__(self, **kwargs):
            pass

        @property
        def messages(self):
            class FakeMessages:
                def create(self, **kwargs):
                    llamada.update(kwargs)
                    return _respuesta_anthropic()

            return FakeMessages()

    monkeypatch.setattr("anthropic.Anthropic", FakeAnthropic)

    llm_service.generate_estimation(REQUEST)

    assert REQUEST.description not in llamada["system"]
    assert llamada["messages"] == [
        {
            "role": "user",
            "content": (
                f"<project_description>\n{REQUEST.description}\n</project_description>"
                "\n\nTipo de proyecto seleccionado: web_saas.\n"
                "Genera la estimación siguiendo las reglas del mensaje de sistema."
            ),
        }
    ]


def test_openai_respuesta_truncada_lanza_error(
    monkeypatch: pytest.MonkeyPatch, settings_openai
) -> None:
    class FakeOpenAI:
        def __init__(self, **kwargs):
            pass

        @property
        def chat(self):
            class FakeCompletions:
                def create(self, **kwargs):
                    return _respuesta_openai(finish_reason="length")

            return types.SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)

    with pytest.raises(LLMServiceError, match="trunc"):
        llm_service.generate_estimation(REQUEST)


def test_openai_respuesta_vacia_lanza_error(
    monkeypatch: pytest.MonkeyPatch, settings_openai
) -> None:
    class FakeOpenAI:
        def __init__(self, **kwargs):
            pass

        @property
        def chat(self):
            class FakeCompletions:
                def create(self, **kwargs):
                    return _respuesta_openai(content="")

            return types.SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)

    with pytest.raises(LLMServiceError, match="vac"):
        llm_service.generate_estimation(REQUEST)


def test_anthropic_truncamiento_lanza_error(
    monkeypatch: pytest.MonkeyPatch, settings_anthropic
) -> None:
    class FakeAnthropic:
        def __init__(self, **kwargs):
            pass

        @property
        def messages(self):
            class FakeMessages:
                def create(self, **kwargs):
                    return _respuesta_anthropic(stop_reason="max_tokens")

            return FakeMessages()

    monkeypatch.setattr("anthropic.Anthropic", FakeAnthropic)

    with pytest.raises(LLMServiceError, match="trunc"):
        llm_service.generate_estimation(REQUEST)
