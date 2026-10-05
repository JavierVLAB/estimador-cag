"""Configuración del servicio.

Este es el único módulo que lee variables de entorno. El resto del código
importa `settings` desde aquí, de forma que cambiar de dónde viene la
configuración no obliga a tocar routers, servicios ni contexto.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    # La versión se decide en el backend. El cliente HTTP nunca puede escoger
    # las instrucciones que se mandan al proveedor.
    llm_prompt_version: Literal["v1", "v2", "v3"] = "v1"

    # Memoria conversacional. El estado vive en un diccionario del proceso: se
    # pierde al reiniciar y no se comparte entre workers. Son topes de coste y
    # de latencia, no de corrección.
    session_max_turns: int = 6

    # Adjuntos. Los tres topes atacan el riesgo en puntos distintos: los bytes
    # evitan leer un archivo desmedido en memoria, los caracteres acotan lo que
    # llega al prompt, y el número de archivos acota el caso de muchos
    # documentos pequeños que en conjunto desbordan.
    max_attachment_bytes: int = 10_000_000
    max_attachment_chars: int = 20_000
    max_attachments_per_request: int = 5

    # Límites y comportamiento de la llamada al LLM. Sin un timeout explícito
    # el SDK usa 600 segundos con varios reintentos, y un proveedor atascado
    # retendría un worker durante media hora.
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 2
    llm_max_output_tokens: int = 2000

    # Dirección del API al que se conecta la interfaz Streamlit. Se conserva
    # separada de la configuración del proveedor: la interfaz nunca llama al
    # proveedor LLM directamente.
    estimator_api_base_url: str = "http://localhost:8000"

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
