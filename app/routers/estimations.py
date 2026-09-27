"""Endpoint de estimación.

Esta capa solo se ocupa del transporte HTTP: valida la entrada, llama al
servicio y traduce el resultado (o el fallo) a una respuesta.
"""

import logging

from fastapi import APIRouter, HTTPException, status

from app.schemas.estimation import EstimationRequest, EstimationResponse, TokenUsage
from app.services import llm_service
from app.services.llm_service import LLMServiceError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["estimaciones"])


@router.post(
    "/estimate",
    response_model=EstimationResponse,
    summary="Genera una estimación guiada de un proyecto",
    description=(
        "Recibe la descripción del proyecto, su tipo, el nivel de detalle y el "
        "formato de salida. Genera una estimación Markdown con los prompts "
        "versionados del sistema."
    ),
)
def estimate(peticion: EstimationRequest) -> EstimationResponse:
    try:
        resultado = llm_service.generate_estimation(peticion)
    except LLMServiceError:
        # El detalle técnico va al log; al cliente solo le llega el motivo,
        # para no filtrar trazas ni credenciales en la respuesta. Un error de
        # programación propio NO se captura aquí: debe salir como 500 para no
        # confundirlo con un fallo del proveedor.
        logger.exception("Fallo al generar la estimación con el proveedor LLM")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="El proveedor LLM no pudo generar la estimación.",
        ) from None

    return EstimationResponse(
        text=resultado.estimation,
        prompt_version=resultado.prompt_version,
        model=resultado.model,
        provider=resultado.provider,
        usage=TokenUsage(
            input_tokens=resultado.usage.input_tokens,
            output_tokens=resultado.usage.output_tokens,
            total_tokens=resultado.usage.total_tokens,
        ),
    )
