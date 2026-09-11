"""Aplicación FastAPI del estimador CAG."""

import logging

from fastapi import FastAPI

from app.config import settings
from app.routers import estimations

logging.basicConfig(level=settings.log_level.upper())

app = FastAPI(
    title="Estimador CAG",
    version="1.0.0",
    description=(
        "Genera estimaciones de software a partir de la transcripción de una "
        "reunión con el cliente.\n\n"
        "Usa arquitectura CAG: las estimaciones de referencia viajan completas "
        "en el prompt de cada llamada, sin base de datos ni recuperación."
    ),
)

app.include_router(estimations.router, prefix="/api/v1")


@app.get("/health", tags=["estado"], summary="Comprueba que el servicio está operativo")
def health() -> dict[str, str]:
    """No consulta al LLM: solo confirma que la aplicación responde."""
    return {"status": "ok", "environment": settings.app_env}
