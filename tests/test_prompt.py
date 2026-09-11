"""Tests del system prompt: verifican la inyección del contexto sin llamar al LLM."""

from app.context.examples import ESTIMATION_EXAMPLES
from app.services.llm_service import build_system_prompt


def test_el_prompt_incluye_todos_los_ejemplos() -> None:
    prompt = build_system_prompt()

    for ejemplo in ESTIMATION_EXAMPLES:
        assert ejemplo.meeting_summary in prompt
        assert ejemplo.estimation in prompt


def test_hay_al_menos_dos_ejemplos() -> None:
    assert len(ESTIMATION_EXAMPLES) >= 2
