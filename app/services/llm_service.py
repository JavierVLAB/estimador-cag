"""Generación de estimaciones mediante un LLM.

Este módulo no conoce HTTP ni FastAPI. Recibe una petición tipada y renderiza
los mensajes versionados antes de entregarlos por separado al proveedor.
"""

import hashlib
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field

from app import config
from app.prompts.loader import PROMPT_VERSION, render_estimation_prompt
from app.schemas.estimation import EstimationRequest

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TokenUsage:
    """Consumo de tokens de una llamada al LLM, normalizado entre proveedores.

    Cada proveedor expone el consumo con una nomenclatura distinta:
    `prompt_tokens/completion_tokens` en OpenAI y `input_tokens/output_tokens`
    en Anthropic. Este modelo los unifica en un solo contrato.
    """

    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class EstimationResult:
    """Resultado de una estimación, independiente del transporte HTTP."""

    estimation: str
    model: str
    provider: str
    usage: TokenUsage
    prompt_version: str = PROMPT_VERSION


@dataclass
class EstimationStream:
    """Estimación en streaming: itera los fragmentos de texto del modelo.

    En la construcción ya se conoce modelo y proveedor, pero el `usage` solo
    puede completarse cuando el flujo se agota: cada proveedor entrega el
    consumo de tokens en el último fragmento de la transmisión. Ser un
    iterable de strings lo hace compatible con `st.write_stream` sin que la
    capa de interfaz conozca los SDK.
    """

    model: str
    provider: str
    usage: TokenUsage | None = None
    prompt_version: str = PROMPT_VERSION
    _chunks: Iterator[str] = field(init=False, repr=False)

    def __iter__(self) -> Iterator[str]:
        yield from self._chunks


class ProveedorNoSoportadoError(ValueError):
    """El valor de LLM_PROVIDER no corresponde a ningún proveedor implementado."""


class LLMServiceError(Exception):
    """La llamada al proveedor falló o devolvió una respuesta no utilizable.

    Es la excepción que la capa de API debe traducir a un código HTTP; el
    detalle interno se loguea pero no viaja al cliente.
    """


def generate_estimation(request: EstimationRequest) -> EstimationResult:
    """Genera la estimación para una petición guiada usando el proveedor configurado.

    Los fallos del proveedor y las respuestas no utilizables se lanzan como
    `LLMServiceError`; traducirlos a un código HTTP es responsabilidad de la
    capa de API.
    """
    settings = config.settings
    prompt_version = settings.llm_prompt_version
    system_prompt, contenido_usuario = render_estimation_prompt(
        request, version=prompt_version
    )
    _log_prompt_metadata(
        version=prompt_version,
        provider=settings.llm_provider,
        model=settings.llm_model,
        system_prompt=system_prompt,
        user_prompt=contenido_usuario,
    )

    if settings.llm_provider == "openai":
        estimation, usage = _generate_openai(system_prompt, contenido_usuario)
    elif settings.llm_provider == "anthropic":
        estimation, usage = _generate_anthropic(system_prompt, contenido_usuario)
    else:
        raise ProveedorNoSoportadoError(
            f"LLM_PROVIDER='{settings.llm_provider}' no está soportado. "
            "Valores admitidos: 'openai', 'anthropic'."
        )

    return EstimationResult(
        estimation=estimation,
        model=settings.llm_model,
        provider=settings.llm_provider,
        usage=usage,
        prompt_version=prompt_version,
    )


def generate_estimation_stream(request: EstimationRequest) -> EstimationStream:
    """Genera la estimación en streaming para una petición guiada.

    Reutiliza exactamente el mismo render versionado y configuración que
    `generate_estimation`: la interfaz interactiva no debe divergir del
    endpoint CAG. Cada proveedor se implementa como un generador que vuelca el
    consumo de tokens en `flujo.usage` al terminar.
    """
    settings = config.settings
    prompt_version = settings.llm_prompt_version
    system_prompt, contenido_usuario = render_estimation_prompt(
        request, version=prompt_version
    )
    _log_prompt_metadata(
        version=prompt_version,
        provider=settings.llm_provider,
        model=settings.llm_model,
        system_prompt=system_prompt,
        user_prompt=contenido_usuario,
    )

    flujo = EstimationStream(
        model=settings.llm_model,
        provider=settings.llm_provider,
        prompt_version=prompt_version,
    )

    if settings.llm_provider == "openai":
        flujo._chunks = _generate_openai_stream(system_prompt, contenido_usuario, flujo)
    elif settings.llm_provider == "anthropic":
        flujo._chunks = _generate_anthropic_stream(
            system_prompt, contenido_usuario, flujo
        )
    else:
        raise ProveedorNoSoportadoError(
            f"LLM_PROVIDER='{settings.llm_provider}' no está soportado. "
            "Valores admitidos: 'openai', 'anthropic'."
        )

    return flujo


def _log_prompt_metadata(
    *,
    version: str,
    provider: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> None:
    """Registra metadatos auditables sin retener el contenido del prompt.

    El separador nulo evita ambigüedades al calcular la huella de los dos
    mensajes. Las longitudes sirven para detectar cambios de tamaño sin
    escribir la descripción ni las instrucciones en los logs.
    """
    prompt_sha256 = hashlib.sha256(
        system_prompt.encode("utf-8") + b"\0" + user_prompt.encode("utf-8")
    ).hexdigest()
    logger.info(
        "Prompt de estimación preparado: version=%s provider=%s model=%s "
        "sha256=%s system_chars=%d user_chars=%d total_chars=%d",
        version,
        provider,
        model,
        prompt_sha256,
        len(system_prompt),
        len(user_prompt),
        len(system_prompt) + len(user_prompt),
        extra={
            "prompt_version": version,
            "llm_provider": provider,
            "llm_model": model,
            "prompt_sha256": prompt_sha256,
            "system_prompt_characters": len(system_prompt),
            "user_prompt_characters": len(user_prompt),
            "prompt_characters": len(system_prompt) + len(user_prompt),
        },
    )


def _generate_openai(system_prompt: str, contenido_usuario: str) -> tuple[str, TokenUsage]:
    """Llama a OpenAI. El cliente se crea aquí para no mantener estado global.

    El timeout y los reintentos explícitos vienen de Settings: sin ellos, el
    SDK usa 600 segundos y esperaría media hora ante un proveedor atascado.
    """
    from openai import OpenAI

    settings = config.settings
    client = OpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )

    response = client.chat.completions.create(
        model=settings.llm_model,
        max_tokens=settings.llm_max_output_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": contenido_usuario},
        ],
    )

    eleccion = response.choices[0]
    if eleccion.finish_reason == "length":
        raise LLMServiceError(
            f"La respuesta se truncó en {settings.llm_max_output_tokens} tokens de salida."
        )
    contenido = eleccion.message.content
    if not contenido:
        raise LLMServiceError("El modelo devolvió una respuesta vacía.")

    uso = response.usage or {}
    input_tokens = getattr(uso, "prompt_tokens", 0)
    output_tokens = getattr(uso, "completion_tokens", 0)
    return contenido, TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=getattr(uso, "total_tokens", input_tokens + output_tokens),
    )


def _generate_openai_stream(
    system_prompt: str, contenido_usuario: str, flujo: EstimationStream
) -> Iterator[str]:
    """Emite la estimación por fragmentos con OpenAI.

    `stream_options={"include_usage": True}` añade un chunk final sin texto
    que trae el consumo de tokens en `usage`; ese chunk tiene `choices` vacío
    y por eso `delta.content` nunca se emite vacío. El truncamiento y la
    respuesta vacía se detectan al final del flujo, igual que en la versión
    no-streaming, de modo que nunca se entrega texto incompleto como válido.
    """
    from openai import OpenAI

    settings = config.settings
    client = OpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )

    stream = client.chat.completions.create(
        model=settings.llm_model,
        max_tokens=settings.llm_max_output_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": contenido_usuario},
        ],
        stream=True,
        stream_options={"include_usage": True},
    )

    texto_acumulado: list[str] = []
    finish_reason = None
    for chunk in stream:
        if chunk.usage:
            uso = chunk.usage
            flujo.usage = TokenUsage(
                input_tokens=uso.prompt_tokens,
                output_tokens=uso.completion_tokens,
                total_tokens=uso.total_tokens,
            )
        if chunk.choices:
            eleccion = chunk.choices[0]
            if eleccion.delta.content:
                texto_acumulado.append(eleccion.delta.content)
                yield eleccion.delta.content
            if eleccion.finish_reason:
                finish_reason = eleccion.finish_reason

    if finish_reason == "length":
        raise LLMServiceError(
            f"La respuesta se truncó en {settings.llm_max_output_tokens} tokens de salida."
        )
    if not texto_acumulado:
        raise LLMServiceError("El modelo devolvió una respuesta vacía.")


def _generate_anthropic(
    system_prompt: str, contenido_usuario: str
) -> tuple[str, TokenUsage]:
    """Llama a Anthropic.

    A diferencia de OpenAI, el system prompt es un parámetro propio y no un
    mensaje más, y `max_tokens` es obligatorio.
    """
    import anthropic

    settings = config.settings
    client = anthropic.Anthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )

    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=settings.llm_max_output_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": contenido_usuario}],
    )

    if response.stop_reason == "max_tokens":
        raise LLMServiceError(
            f"La respuesta se truncó en {settings.llm_max_output_tokens} tokens de salida."
        )
    # La respuesta es una lista de bloques; solo nos interesa el texto.
    texto = "".join(bloque.text for bloque in response.content if bloque.type == "text")
    if not texto:
        raise LLMServiceError("El modelo devolvió una respuesta sin texto.")

    uso = response.usage
    input_tokens = getattr(uso, "input_tokens", 0)
    output_tokens = getattr(uso, "output_tokens", 0)
    return texto, TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
    )


def _generate_anthropic_stream(
    system_prompt: str, contenido_usuario: str, flujo: EstimationStream
) -> Iterator[str]:
    """Emite la estimación por fragmentos con Anthropic.

    El bloque `with` cierra correctamente el stream al terminar o al propagar
    un error. `get_final_message()` expone el mensaje completo: `stop_reason`
    (para detectar truncamiento) y `usage` (para volcarlo en `flujo`).
    """
    import anthropic

    settings = config.settings
    client = anthropic.Anthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )

    with client.messages.stream(
        model=settings.llm_model,
        max_tokens=settings.llm_max_output_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": contenido_usuario}],
    ) as stream:
        texto_acumulado: list[str] = []
        for texto in stream.text_stream:
            texto_acumulado.append(texto)
            yield texto

        final = stream.get_final_message()
        uso = final.usage
        flujo.usage = TokenUsage(
            input_tokens=uso.input_tokens,
            output_tokens=uso.output_tokens,
            total_tokens=uso.input_tokens + uso.output_tokens,
        )

        if final.stop_reason == "max_tokens":
            raise LLMServiceError(
                f"La respuesta se truncó en {settings.llm_max_output_tokens} tokens de salida."
            )
        if not texto_acumulado:
            raise LLMServiceError("El modelo devolvió una respuesta sin texto.")
