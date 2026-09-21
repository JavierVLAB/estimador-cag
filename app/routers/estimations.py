"""Endpoint de estimación.

Esta capa solo se ocupa del transporte HTTP: valida la entrada, llama al
servicio y traduce el resultado (o el fallo) a una respuesta.
"""

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.services import llm_service
from app.services.llm_service import LLMServiceError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["estimaciones"])


class EstimationRequest(BaseModel):
    """Petición de estimación."""

    transcription: str = Field(
        min_length=1,
        max_length=50_000,
        description="Texto de la transcripción de la reunión con el cliente.",
        examples=[
            "En la reunión con el equipo de marketing, el cliente explicó que "
            "necesita una landing page con formulario de contacto e integración "
            "con su CRM actual (HubSpot)."
        ],
    )

    @field_validator("transcription")
    @classmethod
    def no_vacia(cls, valor: str) -> str:
        """Rechaza transcripciones en blanco antes de gastar una llamada al LLM."""
        if not valor.strip():
            raise ValueError("La transcripción no puede estar vacía.")
        return valor


class TokenUsage(BaseModel):
    """Metadatos de consumo de tokens de la llamada al LLM."""

    input_tokens: int = Field(ge=0, description="Tokens de entrada consumidos.")
    output_tokens: int = Field(ge=0, description="Tokens de salida generados.")
    total_tokens: int = Field(ge=0, description="Tokens totales de la llamada.")


class EstimationResponse(BaseModel):
    """Estimación generada."""

    estimation: str = Field(description="La estimación generada, en formato markdown.")
    model: str = Field(description="Modelo utilizado para generarla.")
    provider: str = Field(description="Proveedor utilizado: 'openai' o 'anthropic'.")
    usage: TokenUsage = Field(description="Consumo de tokens de la llamada al LLM.")


@router.post(
    "/estimate",
    response_model=EstimationResponse,
    summary="Genera una estimación a partir de una transcripción",
    description=(
        "Recibe la transcripción de una reunión, la envía al LLM junto con las "
        "estimaciones de referencia del sistema y devuelve la estimación generada."
    ),
)
def estimate(peticion: EstimationRequest) -> EstimationResponse:
    try:
        resultado = llm_service.generate_estimation(peticion.transcription)
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
        estimation=resultado.estimation,
        model=resultado.model,
        provider=resultado.provider,
        usage=TokenUsage(
            input_tokens=resultado.usage.input_tokens,
            output_tokens=resultado.usage.output_tokens,
            total_tokens=resultado.usage.total_tokens,
        ),
    )
