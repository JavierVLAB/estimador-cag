"""Endpoints de la memoria conversacional.

La capa hace el encadenado del turno —resolver sesión, extraer adjuntos,
renderizar, generar, extraer metadata y registrar— y traduce los fallos a
códigos HTTP. La lógica de cada pieza vive en su propio servicio; aquí solo se
coordina.
"""

import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app import config
from app.prompts.loader import render_session_prompt
from app.schemas.estimation import DetailLevel, OutputFormat, ProjectType, TokenUsage
from app.schemas.session import (
    CreateSessionResponse,
    SessionEstimateResponse,
    SessionInfoResponse,
)
from app.services import attachments, llm_service, metadata, sessions
from app.services.llm_service import LLMServiceError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sesiones"])

_store = sessions.SessionStore()

# La versión de plantilla no se configura para este endpoint: v3 es la única que
# recibe el project_metadata y las reglas de continuidad, que es parte del
# contrato de la memoria conversacional. Fijarla aquí evita que un
# `LLM_PROMPT_VERSION=v2` en el entorno convierta el turno en una estimación sin
# contexto ni con variables sin definir. `LLM_PROMPT_VERSION` sigue gobernando
# el endpoint sin estado.
SESSION_PROMPT_VERSION = "v3"


def _error_adjunto(exc: attachments.AttachmentExtractionError) -> HTTPException:
    """Traduce un fallo de adjunto al código que le corresponde.

    Cada tipo tiene su código porque el cliente reacciona distinto: un `413` se
    resuelve resubiendo más pequeño, un `415` cambiando el archivo, y un `422`
    suele significar que hay que avisar de que el archivo llegó roto. El nombre
    del archivo sí viaja en el mensaje; la traza del parser, no.
    """
    if isinstance(exc, attachments.AttachmentTooLargeError):
        codigo = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    elif isinstance(exc, attachments.UnsupportedAttachmentError):
        codigo = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    else:
        codigo = status.HTTP_422_UNPROCESSABLE_CONTENT

    logger.warning("Adjunto rechazado (%s): %s", exc.filename, exc.message)
    return HTTPException(status_code=codigo, detail=exc.message)


def _leer_acotado(archivo: UploadFile, max_bytes: int) -> bytes:
    """Lee como mucho `max_bytes` + 1 byte.

    El byte extra es el que permite distinguir "cabe" de "se pasa" sin leer el
    archivo entero. Sin esto, la comprobación de tamaño de `extract_text` llegaría
    tarde: el contenido ya estaría en memoria, que es justo lo que el tope
    pretendía evitar.
    """
    return archivo.file.read(max_bytes + 1)


@router.post(
    "",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crea una sesión conversacional",
    description=(
        "Devuelve un identificador de sesión. El historial empieza vacío y vive "
        "en memoria del proceso: se pierde al reiniciar el servidor."
    ),
)
def create_session() -> CreateSessionResponse:
    return CreateSessionResponse(session_id=_store.create().session_id)


@router.get(
    "/{session_id}",
    response_model=SessionInfoResponse,
    summary="Consulta el estado de una sesión",
    description=(
        "Devuelve el project_metadata conocido, el número de mensajes retenidos "
        "y el límite de turnos. No llama al proveedor."
    ),
)
def get_session(session_id: str) -> SessionInfoResponse:
    session = _obtener_sesion(session_id)

    return SessionInfoResponse(
        session_id=session.session_id,
        metadata=session.metadata,
        message_count=len(session.history.to_messages()),
        max_turns=_store.max_turns,
    )


def _obtener_sesion(session_id: str) -> sessions.Session:
    """Resuelve la sesión o responde 404.

    No la recrea: dejar que este endpoint fabricara una sesión ante un id
    desconocido haría que la interfaz conversara con un historial que el backend
    nunca vio, que es peor que un error claro.
    """
    try:
        return _store.get_or_404(session_id)
    except sessions.SessionNotFoundError:
        logger.info("Se pidió una sesión inexistente: %s", session_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe la sesión {session_id}.",
        ) from None


@router.post(
    "/{session_id}/estimate",
    response_model=SessionEstimateResponse,
    summary="Genera la estimación de un turno de la conversación",
    description=(
        "Añade la transcripción del turno al historial de la sesión y devuelve la "
        "estimación junto con el project_metadata actualizado. Acepta adjuntos PDF "
        "y Word, cuyo texto se extrae en el servidor."
    ),
)
def estimate_turn(
    session_id: str,
    description: str = Form(..., description="Transcripción de este turno."),
    project_type: ProjectType = Form(...),
    detail_level: DetailLevel = Form(...),
    output_format: OutputFormat = Form(...),
    files: list[UploadFile] | None = File(default=None),
) -> SessionEstimateResponse:
    session = _obtener_sesion(session_id)
    settings = config.settings

    adjuntos = files or []
    if len(adjuntos) > settings.max_attachments_per_request:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Se han recibido {len(adjuntos)} adjuntos y el máximo por turno "
                f"es {settings.max_attachments_per_request}."
            ),
        )

    textos: list[tuple[str, str]] = []
    for archivo in adjuntos:
        if not archivo.filename:
            continue
        try:
            texto = attachments.extract_text(
                filename=archivo.filename,
                content=_leer_acotado(archivo, settings.max_attachment_bytes),
                max_bytes=settings.max_attachment_bytes,
                max_chars=settings.max_attachment_chars,
            )
        except attachments.AttachmentExtractionError as exc:
            raise _error_adjunto(exc) from None
        textos.append((archivo.filename, texto))

    transcripcion = attachments.enrich_transcript(transcript=description, attachments=textos)

    # El historial se lee antes de añadir este turno, y el mensaje de este turno
    # se concatena aparte: `messages` es lo que viaja al proveedor, no el array
    # que la sesión tenía guardado.
    historial = session.history.to_messages()

    system_prompt, contenido_usuario = render_session_prompt(
        transcript=transcripcion,
        project_type=project_type.value,
        detail_level=detail_level.value,
        output_format=output_format.value,
        metadata=session.metadata,
        version=SESSION_PROMPT_VERSION,
    )

    mensajes = [*historial, {"role": "user", "content": contenido_usuario}]

    try:
        completion = llm_service.generate_turn(
            system_prompt=system_prompt, messages=mensajes
        )
    except LLMServiceError:
        logger.exception("Fallo al generar el turno con el proveedor LLM")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="El proveedor LLM no pudo generar la estimación.",
        ) from None

    conversacion = "\n".join(
        f"{mensaje['role']}: {mensaje['content']}" for mensaje in mensajes
    )
    session.metadata = metadata.extract_and_merge(
        transcript=transcripcion,
        previous_metadata=session.metadata,
        conversation=conversacion,
    )
    turnos = session.record_turn(user=transcripcion, assistant=completion.text)

    return SessionEstimateResponse(
        text=completion.text,
        prompt_version=SESSION_PROMPT_VERSION,
        model=completion.model,
        provider=completion.provider,
        usage=TokenUsage(
            input_tokens=completion.usage.input_tokens,
            output_tokens=completion.usage.output_tokens,
            total_tokens=completion.usage.total_tokens,
        ),
        metadata=session.metadata,
        turns_kept=turnos,
    )