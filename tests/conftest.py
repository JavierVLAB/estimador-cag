"""Configuración común de los tests.

Ningún test llama al LLM: el servicio se sustituye siempre por un doble.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
