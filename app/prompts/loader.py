"""Render de las plantillas versionadas de estimación."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.schemas.estimation import EstimationRequest
from app.schemas.session import ProjectMetadata

PROMPT_VERSION = "v1"
METADATA_EXTRACTION_VERSION = "v1"

# La versión que usan los turnos de sesión. No se configurable a propósito: v3 es
# la única que recibe el project_metadata y las reglas de continuidad, que es
# parte del contrato de la memoria conversacional. Fijarla aquí evita que un
# `LLM_PROMPT_VERSION=v2` convierta el turno en una estimación sin contexto y con
# variables sin definir. `LLM_PROMPT_VERSION` sigue gobernando el endpoint sin
# estado.
SESSION_PROMPT_VERSION = "v3"

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


def render_session_prompt(
    *,
    transcript: str,
    project_type: str,
    detail_level: str,
    output_format: str,
    metadata: ProjectMetadata,
    version: str,
) -> tuple[str, str]:
    """Mensajes de un turno de conversación.

    El de sistema se renderiza con la metadata del momento, no con la del
    primer turno: por eso se re-renderiza en cada llamada en vez de guardarse
    en el historial. Al recibir `metadata` como objeto y no como diccionario,
    la plantilla decide con `is_empty()` cómo presentar el primer turno, y no
    dependemos de que el llamador recuerde ese caso.

    El mensaje de usuario envuelve la transcripción del turno, ya enriquecida
    con los adjuntos. En el historial se guarda este mismo mensaje renderizado,
    no la transcripción desnuda: así todos los turnos anteriores llevan las
    mismas vallas de adjunto y el modelo no tiene que adivinar dónde acaba el
    material de referencia.
    """
    context = {
        "transcript": transcript,
        "project_type": project_type,
        "detail_level": detail_level,
        "output_format": output_format,
        "metadata": metadata,
    }
    system = _environment.get_template(f"estimation/{version}/system.j2").render(**context)
    user = _environment.get_template(f"estimation/{version}/user.j2").render(**context)
    return _clean_rendered_text(system), _clean_rendered_text(user)


def render_metadata_extraction_prompt(
    *,
    transcript: str,
    conversation: str = "",
    version: str = METADATA_EXTRACTION_VERSION,
) -> tuple[str, str]:
    """Mensajes del extractor de `project_metadata`.

    Se lleva el historial completo, no solo el último turno, porque un dato
    confirmado en el turno 1 y no repetido en el 4 sigue siendo parte del
    contexto que hay que consolidar. Es el servicio quien decide si truncarlo.
    """
    context = {"transcript": transcript, "conversation": conversation}
    system = _environment.get_template(
        f"metadata_extraction/{version}/system.j2"
    ).render(**context)
    user = _environment.get_template(f"metadata_extraction/{version}/user.j2").render(
        **context
    )
    return _clean_rendered_text(system), _clean_rendered_text(user)
