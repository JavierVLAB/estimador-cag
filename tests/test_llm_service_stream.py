"""Tests del streaming de `app/services/llm_service.py` con dobles del SDK.

Repiten el patrón de `test_llm_service.py` para la variante streaming: el SDK
se sustituye por objetos falsos y ningún test contacta con un proveedor real.
"""

import re
import types

import anthropic
import pytest

from app import config
from app.services import llm_service
from app.services.llm_service import LLMServiceError, TokenUsage, build_system_prompt

TRANSCRIPCION = "El cliente quiere una landing page."

USAGE_OPENAI = types.SimpleNamespace(
    prompt_tokens=11, completion_tokens=9, total_tokens=20
)
USAGE_ANTHROPIC = types.SimpleNamespace(input_tokens=9, output_tokens=5)


@pytest.fixture
def settings_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm_service.config,
        "settings",
        config.Settings(_env_file=None, llm_provider="openai", llm_max_output_tokens=100),
    )


@pytest.fixture
def settings_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm_service.config,
        "settings",
        config.Settings(_env_file=None, llm_provider="anthropic", llm_max_output_tokens=100),
    )


def _chunk_openai(
    *,
    content: str | None = None,
    finish_reason: str | None = None,
    usage: types.SimpleNamespace | None = None,
) -> types.SimpleNamespace:
    """Un fragmento del stream de OpenAI.

    Los chunks con `usage` final (habilitado con `stream_options`) llegan con
    `choices` vacío; solo los chunks de contenido llevan `delta`.
    """
    choices = []
    if content is not None or finish_reason is not None:
        choices.append(
            types.SimpleNamespace(
                delta=types.SimpleNamespace(content=content),
                finish_reason=finish_reason,
            )
        )
    return types.SimpleNamespace(usage=usage, choices=choices)


def _cliente_openai(monkeypatch: pytest.MonkeyPatch, chunks: list) -> dict:
    """Sustituye `openai.OpenAI` y captura los kwargs de `create`."""
    llamada: dict = {}

    class FakeCompletions:
        def create(self, **kwargs):
            llamada.update(kwargs)
            return chunks

    class FakeOpenAI:
        def __init__(self, **kwargs):
            pass

        @property
        def chat(self):
            return types.SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)
    return llamada


def _cliente_anthropic(
    monkeypatch: pytest.MonkeyPatch,
    textos: list[str],
    stop_reason: str,
    usage: types.SimpleNamespace = USAGE_ANTHROPIC,
) -> dict:
    """Sustituye `anthropic.Anthropic` y captura los kwargs de `messages.stream`."""
    llamada: dict = {}

    class FakeMessages:
        def stream(self, **kwargs):
            llamada.update(kwargs)
            return FakeStreamManager(textos, stop_reason, usage)

    class FakeAnthropic:
        def __init__(self, **kwargs):
            pass

        @property
        def messages(self):
            return FakeMessages()

    monkeypatch.setattr("anthropic.Anthropic", FakeAnthropic)
    return llamada


class FakeStreamManager:
    """Réplica del gestor de streaming de Anthropic (admite `with`)."""

    def __init__(self, textos, stop_reason, usage):
        self._textos = textos
        self._stop_reason = stop_reason
        self._usage = usage

    def __enter__(self):
        return SimpleStream(self._textos, self._stop_reason, self._usage)

    def __exit__(self, *exc):
        return False


class SimpleStream:
    """Réplica del objeto `MessageStream`: texto por fragmentos y mensaje final."""

    def __init__(self, textos, stop_reason, usage):
        self.text_stream = iter(textos)
        self._stop_reason = stop_reason
        self._usage = usage

    def get_final_message(self):
        return types.SimpleNamespace(
            stop_reason=self._stop_reason, usage=self._usage
        )


def test_openai_emite_los_chunks_en_orden(
    monkeypatch: pytest.MonkeyPatch, settings_openai
) -> None:
    chunks = [
        _chunk_openai(content="## "),
        _chunk_openai(content="Estimación"),
        _chunk_openai(content=": **40 h**"),
        _chunk_openai(usage=USAGE_OPENAI),
    ]
    _cliente_openai(monkeypatch, chunks)

    flujo = llm_service.generate_estimation_stream(TRANSCRIPCION)

    assert list(flujo) == ["## ", "Estimación", ": **40 h**"]


def test_anthropic_emite_los_chunks_en_orden(
    monkeypatch: pytest.MonkeyPatch, settings_anthropic
) -> None:
    _cliente_anthropic(monkeypatch, ["## ", "Estimación", ": **40 h**"], "end_turn")

    flujo = llm_service.generate_estimation_stream(TRANSCRIPCION)

    assert list(flujo) == ["## ", "Estimación", ": **40 h**"]


def test_stream_reutiliza_el_system_prompt_y_el_delimitador(
    monkeypatch: pytest.MonkeyPatch, settings_openai
) -> None:
    llamada = _cliente_openai(
        monkeypatch,
        [_chunk_openai(content="## Estimación"), _chunk_openai(usage=USAGE_OPENAI)],
    )

    flujo = llm_service.generate_estimation_stream(TRANSCRIPCION)
    list(flujo)

    assert llamada["stream"] is True
    assert llamada["stream_options"] == {"include_usage": True}
    assert llamada["messages"][0]["content"] == build_system_prompt()
    contenido_usuario = llamada["messages"][1]["content"]
    assert contenido_usuario.startswith("<datos-")
    assert re.search(r"</datos-[0-9a-f]+>$", contenido_usuario)
    assert TRANSCRIPCION in contenido_usuario


def test_openai_truncado_lanza_error(
    monkeypatch: pytest.MonkeyPatch, settings_openai
) -> None:
    _cliente_openai(
        monkeypatch,
        [
            _chunk_openai(content="## Estimación"),
            _chunk_openai(content="", finish_reason="length", usage=USAGE_OPENAI),
        ],
    )

    flujo = llm_service.generate_estimation_stream(TRANSCRIPCION)

    with pytest.raises(LLMServiceError, match="trunc"):
        list(flujo)


def test_openai_sin_texto_lanza_error(
    monkeypatch: pytest.MonkeyPatch, settings_openai
) -> None:
    _cliente_openai(monkeypatch, [_chunk_openai(usage=USAGE_OPENAI)])

    flujo = llm_service.generate_estimation_stream(TRANSCRIPCION)

    with pytest.raises(LLMServiceError, match="vac"):
        list(flujo)


def test_anthropic_truncado_lanza_error(
    monkeypatch: pytest.MonkeyPatch, settings_anthropic
) -> None:
    _cliente_anthropic(monkeypatch, ["## Estimación"], "max_tokens")

    flujo = llm_service.generate_estimation_stream(TRANSCRIPCION)

    with pytest.raises(LLMServiceError, match="trunc"):
        list(flujo)


def test_anthropic_sin_texto_lanza_error(
    monkeypatch: pytest.MonkeyPatch, settings_anthropic
) -> None:
    _cliente_anthropic(monkeypatch, [], "end_turn")

    flujo = llm_service.generate_estimation_stream(TRANSCRIPCION)

    with pytest.raises(LLMServiceError, match="sin texto"):
        list(flujo)


def test_el_usage_se_expone_al_agotarse_el_stream_openai(
    monkeypatch: pytest.MonkeyPatch, settings_openai
) -> None:
    _cliente_openai(
        monkeypatch,
        [_chunk_openai(content="## Estimación"), _chunk_openai(usage=USAGE_OPENAI)],
    )

    flujo = llm_service.generate_estimation_stream(TRANSCRIPCION)
    list(flujo)

    assert flujo.usage == TokenUsage(input_tokens=11, output_tokens=9, total_tokens=20)
    assert flujo.model == "gpt-4o-mini"
    assert flujo.provider == "openai"


def test_el_usage_se_expone_al_agotarse_el_stream_anthropic(
    monkeypatch: pytest.MonkeyPatch, settings_anthropic
) -> None:
    _cliente_anthropic(monkeypatch, ["## Estimación"], "end_turn")

    flujo = llm_service.generate_estimation_stream(TRANSCRIPCION)
    list(flujo)

    assert flujo.usage == TokenUsage(input_tokens=9, output_tokens=5, total_tokens=14)
    assert flujo.model == "gpt-4o-mini"
    assert flujo.provider == "anthropic"