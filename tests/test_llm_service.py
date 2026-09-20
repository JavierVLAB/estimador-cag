"""Tests de `app/services/llm_service.py` con clientes SDK sustituidos por dobles.

Ningún test contacta con un proveedor real: se sustituye la clase del SDK y se
verifica con qué parámetros se construye y se llama.
"""

import re
import types

import anthropic
import pytest

from app import config
from app.services import llm_service
from app.services.llm_service import LLMServiceError

TRANSCRIPCION = "El cliente quiere una landing page."


@pytest.fixture
def settings_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configuración fija para el servicio, sin leer el `.env` real."""
    monkeypatch.setattr(
        llm_service.config,
        "settings",
        _settings("openai"),
    )


@pytest.fixture
def settings_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm_service.config,
        "settings",
        _settings("anthropic"),
    )


def _settings(provider: str) -> config.Settings:
    return config.Settings(
        _env_file=None,
        llm_provider=provider,
        llm_timeout_seconds=12.5,
        llm_max_retries=3,
        llm_max_output_tokens=100,
        openai_api_key=None,
        anthropic_api_key=None,
    )


def _respuesta_openai(
    *, finish_reason: str = "stop", content: str = "## Estimación: **40 h**"
):
    return types.SimpleNamespace(
        choices=[
            types.SimpleNamespace(
                finish_reason=finish_reason,
                message=types.SimpleNamespace(content=content),
            )
        ]
    )


def _respuesta_anthropic(
    *, stop_reason: str = "end_turn", bloques: list | None = None
):
    bloques = bloques or [types.SimpleNamespace(type="text", text="## Estimación")]
    return types.SimpleNamespace(stop_reason=stop_reason, content=bloques)


def test_cliente_openai_recibe_timeout_retries_y_max_tokens(
    monkeypatch: pytest.MonkeyPatch, settings_openai
) -> None:
    constructor_kwargs = {}
    create_kwargs = {}

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

    resultado = llm_service.generate_estimation(TRANSCRIPCION)

    assert constructor_kwargs["timeout"] == 12.5
    assert constructor_kwargs["max_retries"] == 3
    assert create_kwargs["max_tokens"] == 100
    assert resultado.estimation == "## Estimación: **40 h**"


def test_la_transcripcion_viaja_delimitada(
    monkeypatch: pytest.MonkeyPatch, settings_openai
) -> None:
    llamada = {}

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

    llm_service.generate_estimation(TRANSCRIPCION)

    contenido_usuario = llamada["messages"][1]["content"]
    assert contenido_usuario.startswith("<datos-")
    assert re.search(r"</datos-[0-9a-f]+>$", contenido_usuario)
    assert TRANSCRIPCION in contenido_usuario


def test_delimitador_distinto_por_peticion() -> None:
    a = llm_service.delimitar_transcripcion("texto")
    b = llm_service.delimitar_transcripcion("texto")
    assert a != b
    assert a.startswith("<datos-") and re.search(r"</datos-[0-9a-f]+>$", a)
    assert "texto" in a


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
        llm_service.generate_estimation(TRANSCRIPCION)


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
        llm_service.generate_estimation(TRANSCRIPCION)


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
        llm_service.generate_estimation(TRANSCRIPCION)