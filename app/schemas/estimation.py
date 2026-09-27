"""Contratos de entrada y salida para una estimación guiada."""

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class ProjectType(str, Enum):
    """Categorías de proyecto que puede seleccionar la persona usuaria."""

    MOBILE_APP = "mobile_app"
    WEB_SAAS = "web_saas"
    INTERNAL_TOOL = "internal_tool"
    DATA_PIPELINE = "data_pipeline"


class DetailLevel(str, Enum):
    """Profundidad solicitada para la estimación."""

    SUMMARY = "summary"
    MEDIUM = "medium"
    DETAILED = "detailed"


class OutputFormat(str, Enum):
    """Presentación solicitada para el resultado en Markdown."""

    PHASES_TABLE = "phases_table"
    LINE_ITEMS = "line_items"
    NARRATIVE = "narrative"


class EstimationRequest(BaseModel):
    """Datos necesarios para generar una estimación guiada."""

    description: str = Field(
        min_length=20,
        max_length=2_000,
        description="Descripción del proyecto o resumen de la reunión.",
    )
    project_type: ProjectType = Field(description="Tipo general de proyecto.")
    detail_level: DetailLevel = Field(description="Nivel de detalle solicitado.")
    output_format: OutputFormat = Field(description="Formato de salida solicitado.")

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, value: object) -> object:
        """No cuenta como descripción el espacio que rodea el texto."""
        return value.strip() if isinstance(value, str) else value


class TokenUsage(BaseModel):
    """Consumo de tokens normalizado para la respuesta HTTP."""

    input_tokens: int = Field(ge=0, description="Tokens de entrada consumidos.")
    output_tokens: int = Field(ge=0, description="Tokens de salida generados.")
    total_tokens: int = Field(ge=0, description="Tokens totales de la llamada.")


class EstimationResponse(BaseModel):
    """Estimación en Markdown y metadatos de la generación."""

    text: str = Field(description="Estimación generada en formato Markdown.")
    prompt_version: str = Field(description="Versión de la plantilla empleada.")
    model: str = Field(description="Modelo utilizado para generarla.")
    provider: str = Field(description="Proveedor que generó la estimación.")
    usage: TokenUsage = Field(description="Consumo de tokens de la llamada.")
