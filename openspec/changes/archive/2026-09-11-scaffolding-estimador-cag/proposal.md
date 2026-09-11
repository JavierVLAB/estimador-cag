## Why

El proyecto está vacío: no existe todavía el servicio que el ejercicio de la Sesión 2 pide entregar. Hace falta el scaffolding funcional de la v1.0 — recibir una transcripción de reunión y devolver una estimación de software generada por un LLM — para poder iterar sobre la calidad del prompt en la sesión en vivo en lugar de dedicarla al setup.

## What Changes

- Se crea el proyecto Python gestionado con `uv` (`pyproject.toml`, Python 3.11+) con las dependencias del enunciado: `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `python-dotenv`, `openai` y `anthropic`.
- Se añade la aplicación FastAPI (`app/main.py`) con título y descripción para Swagger, un `GET /health` y el router de estimaciones montado en `/api/v1`.
- Se añade `POST /api/v1/estimate`: recibe `{ "transcription": "..." }` y devuelve `{ "estimation": "<markdown>", "model": "...", "provider": "..." }`.
- Se añade la configuración centralizada (`app/config.py`) con `pydantic-settings`: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LLM_PROVIDER` (default `openai`), `LLM_MODEL` (default `gpt-4o-mini`), `APP_ENV` (default `development`), `LOG_LEVEL` (default `DEBUG`).
- Se añaden dos proveedores LLM seleccionables por `LLM_PROVIDER`: OpenAI (`gpt-4o-mini`) y Anthropic (`claude-haiku-4-5`).
- Se añade el contexto estático CAG (`app/context/examples.py`): al menos dos ejemplos de estimaciones previas, de tipologías distintas, inyectados en el system prompt en cada llamada.
- Se añade `.env.example` documentando las variables sin valores reales.
- Se añaden tests con el cliente LLM mockeado, sin llamadas reales al proveedor.
- Se reescribe el `README.md` para la versión 1.0: qué hace el sistema, qué es CAG y por qué se usa aquí, el flujo completo, setup con `uv`, variables de entorno y ejemplo `curl`.

Sin cambios que rompan nada: el repositorio no tiene código previo.

## Capabilities

### New Capabilities

- `estimacion-transcripcion`: endpoint HTTP que recibe una transcripción de reunión y devuelve la estimación generada en markdown, con su contrato de request/response y el comportamiento ante errores del proveedor.
- `contexto-cag`: los ejemplos estáticos de estimaciones previas y su inyección en el system prompt en cada llamada, que es el núcleo de la arquitectura CAG.
- `configuracion-proveedores`: carga de configuración desde el entorno y selección del proveedor LLM (OpenAI o Anthropic) con su modelo correspondiente.
- `salud-y-documentacion`: health check y documentación automática de la API (Swagger).

### Modified Capabilities

Ninguna. No existen specs previas en `openspec/specs/`.

## Impact

- **Código nuevo**: `app/` completo (`main.py`, `config.py`, `routers/estimations.py`, `services/llm_service.py`, `context/examples.py`) y `tests/`.
- **Configuración**: `pyproject.toml` nuevo; `.env.example` nuevo. El `.env` real lo gestiona Javi y no se toca.
- **Dependencias**: se introducen `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `python-dotenv`, `openai`, `anthropic` y, para tests, `pytest` y `httpx`.
- **Documentación**: `README.md` pasa de una línea a la documentación de la v1.0.
- **Fuera de alcance explícito**: base de datos, retrieval, vector store, persistencia y caché. La arquitectura CAG es deliberada.
- **Servicios externos**: no se realizan llamadas reales al LLM como parte de este change; la verificación se hace con mocks.
