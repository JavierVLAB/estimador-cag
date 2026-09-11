"""Generación de la estimación mediante un LLM.

Este módulo no conoce HTTP ni FastAPI: recibe texto y devuelve texto. Esa
separación es lo que permitirá, más adelante, sustituir el contexto estático
por recuperación (RAG) sin tocar la capa de API.

La construcción del prompt está separada de la llamada al proveedor porque el
prompt es la pieza que más se itera, y así puede verificarse sin gastar
llamadas al modelo.
"""

from dataclasses import dataclass

from app import config
from app.context.examples import EstimationExample, ESTIMATION_EXAMPLES

INSTRUCCIONES = """Eres un estimador de software senior. A partir de la transcripción de una reunión con un cliente, produces una estimación de esfuerzo realista y accionable.

Sigue estas reglas:

- Desglosa el trabajo en tareas concretas, cada una con sus horas.
- Indica el total de horas, el equipo recomendado y la duración estimada en semanas.
- Enumera los supuestos que has tenido que hacer cuando la transcripción no es explícita.
- Señala los riesgos que puedan desviar la estimación.
- Si la transcripción no aporta información suficiente para estimar algo, dilo en los supuestos en lugar de inventar requisitos.
- Responde en markdown y en español, con el mismo formato y nivel de detalle que los ejemplos.
- Responde únicamente con la estimación, sin saludos ni comentarios previos."""


@dataclass(frozen=True)
class EstimationResult:
    """Resultado de una estimación, independiente del transporte HTTP."""

    estimation: str
    model: str
    provider: str


class ProveedorNoSoportadoError(ValueError):
    """El valor de LLM_PROVIDER no corresponde a ningún proveedor implementado."""


def build_system_prompt(
    examples: list[EstimationExample] = ESTIMATION_EXAMPLES,
) -> str:
    """Construye el system prompt: instrucciones + estimaciones de referencia.

    Aquí es donde el contexto estático entra en la llamada (arquitectura CAG):
    los ejemplos viajan completos en cada petición.
    """
    bloques = [
        f"### Ejemplo {i}\n\n"
        f"**Reunión:**\n{ejemplo.meeting_summary}\n\n"
        f"**Estimación entregada:**\n{ejemplo.estimation}"
        for i, ejemplo in enumerate(examples, start=1)
    ]
    referencia = "\n\n---\n\n".join(bloques)

    return (
        f"{INSTRUCCIONES}\n\n"
        "## Estimaciones previas de referencia\n\n"
        "Estas son estimaciones reales que hemos entregado antes. Úsalas como "
        "referencia de formato, granularidad y criterio de esfuerzo.\n\n"
        f"{referencia}"
    )


def generate_estimation(transcription: str) -> EstimationResult:
    """Genera la estimación para una transcripción usando el proveedor configurado.

    Los errores del proveedor se dejan propagar: traducirlos a un código HTTP
    es responsabilidad de la capa de API.
    """
    settings = config.settings
    system_prompt = build_system_prompt()

    if settings.llm_provider == "openai":
        estimation = _generate_openai(system_prompt, transcription)
    elif settings.llm_provider == "anthropic":
        estimation = _generate_anthropic(system_prompt, transcription)
    else:
        raise ProveedorNoSoportadoError(
            f"LLM_PROVIDER='{settings.llm_provider}' no está soportado. "
            "Valores admitidos: 'openai', 'anthropic'."
        )

    return EstimationResult(
        estimation=estimation,
        model=settings.llm_model,
        provider=settings.llm_provider,
    )


def _generate_openai(system_prompt: str, transcription: str) -> str:
    """Llama a OpenAI. El cliente se crea aquí para no mantener estado global."""
    from openai import OpenAI

    settings = config.settings
    client = OpenAI(api_key=settings.openai_api_key)

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcription},
        ],
    )
    return response.choices[0].message.content or ""


def _generate_anthropic(system_prompt: str, transcription: str) -> str:
    """Llama a Anthropic.

    A diferencia de OpenAI, el system prompt es un parámetro propio y no un
    mensaje más, y `max_tokens` es obligatorio.
    """
    import anthropic

    settings = config.settings
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": transcription}],
    )
    # La respuesta es una lista de bloques; solo nos interesa el texto.
    return "".join(bloque.text for bloque in response.content if bloque.type == "text")
