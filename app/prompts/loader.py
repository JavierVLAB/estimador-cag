"""Render de las plantillas versionadas de estimación."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.schemas.estimation import EstimationRequest

PROMPT_VERSION = "v1"
_PROMPTS_DIR = Path(__file__).resolve().parent

_environment = Environment(
    loader=FileSystemLoader(_PROMPTS_DIR),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False,
    keep_trailing_newline=False,
)


def _clean_rendered_text(text: str) -> str:
    """Elimina márgenes accidentales, preservando la estructura Markdown."""
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def render_estimation_prompt(
    request: EstimationRequest,
    version: str = PROMPT_VERSION,
) -> tuple[str, str]:
    """Devuelve los mensajes de sistema y usuario, siempre por separado.

    ``StrictUndefined`` hace que una variable mal escrita en las plantillas
    falle aquí, antes de iniciar una llamada al proveedor.
    """
    context = {
        "description": request.description,
        "project_type": request.project_type.value,
        "detail_level": request.detail_level.value,
        "output_format": request.output_format.value,
    }
    system = _environment.get_template(f"estimation/{version}/system.j2").render(
        **context
    )
    user = _environment.get_template(f"estimation/{version}/user.j2").render(
        **context
    )
    return _clean_rendered_text(system), _clean_rendered_text(user)
