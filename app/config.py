"""Configuración del servicio.

Este es el único módulo que lee variables de entorno. El resto del código
importa `settings` desde aquí, de forma que cambiar de dónde viene la
configuración no obliga a tocar routers, servicios ni contexto.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Modelo recomendado para cada proveedor. Se usa solo como referencia en la
# documentación y en los mensajes de error: el modelo efectivo siempre es
# `settings.llm_model`.
MODELOS_RECOMENDADOS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5",
}


class Settings(BaseSettings):
    """Variables de entorno del servicio, cargadas desde `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Credenciales. Son opcionales porque solo hace falta la del proveedor activo:
    # exigir ambas impediría arrancar a quien solo tiene una cuenta.
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Proveedor y modelo. `llm_model` no se deriva del proveedor a propósito:
    # el enunciado lo define como variable independiente para poder probar
    # distintos modelos del mismo proveedor sin tocar código.
    llm_provider: Literal["openai", "anthropic"] = "openai"
    llm_model: str = "gpt-4o-mini"

    app_env: str = "development"
    log_level: str = "DEBUG"


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración, leída una sola vez por proceso.

    La caché permite además que los tests sustituyan la configuración
    limpiándola con `get_settings.cache_clear()`.
    """
    return Settings()


settings = get_settings()
