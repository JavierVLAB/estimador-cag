## 1. Proyecto y dependencias

- [x] 1.1 Crear `pyproject.toml` con `uv`, Python >= 3.11, nombre `estimador-cag` y versión `1.0.0`
- [x] 1.2 Añadir dependencias: `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `python-dotenv`, `openai`, `anthropic`
- [x] 1.3 Añadir dependencias de desarrollo para tests: `pytest`, `httpx`
- [x] 1.4 Crear el árbol de paquetes `app/`, `app/routers/`, `app/services/`, `app/context/` con sus `__init__.py`
- [x] 1.5 Ejecutar `uv sync` y verificar que el entorno se resuelve sin errores

## 2. Configuración

- [x] 2.1 Implementar `app/config.py` con `Settings(BaseSettings)`: `openai_api_key`, `anthropic_api_key`, `llm_provider` (default `openai`), `llm_model` (default `gpt-4o-mini`), `app_env` (default `development`), `log_level` (default `DEBUG`), leyendo desde `.env`
- [x] 2.2 Exponer una instancia `settings` de módulo y comprobar que ningún otro archivo lee el entorno
- [x] 2.3 Crear `.env.example` con todas las variables sin valores reales, documentando que `LLM_MODEL` debe coincidir con el proveedor elegido (`gpt-4o-mini` para OpenAI, `claude-haiku-4-5` para Anthropic)
- [x] 2.4 Verificar que `.env` sigue listado en `.gitignore`

## 3. Contexto CAG

- [x] 3.1 Definir el `dataclass` `EstimationExample(meeting_summary, estimation)` en `app/context/examples.py`
- [x] 3.2 Escribir al menos dos ejemplos de tipologías distintas (plataforma completa e integración acotada) con desglose de tareas, horas, equipo y duración
- [x] 3.3 Comprobar que el módulo no importa `app.config`, `app.services` ni FastAPI

## 4. Servicio LLM

- [x] 4.1 Definir el `dataclass` `EstimationResult(estimation, model, provider)` en `app/services/llm_service.py`
- [x] 4.2 Implementar `build_system_prompt(examples)`: rol de estimador experto + ejemplos renderizados como referencia
- [x] 4.3 Implementar `_generate_openai(system_prompt, transcription)` usando el SDK de OpenAI con `settings.llm_model`
- [x] 4.4 Implementar `_generate_anthropic(system_prompt, transcription)` usando el SDK de Anthropic con `settings.llm_model`
- [x] 4.5 Implementar `generate_estimation(transcription)`: despacha según `settings.llm_provider` y lanza un error claro si el valor no es `openai` ni `anthropic`
- [x] 4.6 Comprobar que el módulo no importa FastAPI

## 5. Endpoint y aplicación

- [x] 5.1 Definir en `app/routers/estimations.py` los schemas `EstimationRequest` (con `transcription` no vacía) y `EstimationResponse` (`estimation`, `model`, `provider`), con descripciones para Swagger
- [x] 5.2 Implementar `POST /estimate` en el router, llamando al servicio y devolviendo el schema de respuesta
- [x] 5.3 Capturar los fallos del proveedor en el router y responder `502` con mensaje claro, sin traza ni credenciales; registrar el detalle en el log
- [x] 5.4 Implementar `app/main.py`: app FastAPI con título y descripción, `GET /health` y router montado con prefijo `/api/v1`
- [x] 5.5 Configurar el logging según `LOG_LEVEL`

## 6. Tests con mock

- [x] 6.1 Crear `tests/` con la configuración mínima de `pytest` y `TestClient`
- [x] 6.2 Test: `GET /health` responde `200`
- [x] 6.3 Test: `POST /api/v1/estimate` con transcripción válida devuelve `200` y los tres campos, con el proveedor mockeado
- [x] 6.4 Test: transcripción ausente o vacía devuelve `422` sin llamar al proveedor
- [x] 6.5 Test: si el proveedor lanza excepción, la respuesta es `502` y no expone la traza
- [x] 6.6 Test: `build_system_prompt` incluye el resumen y la estimación de cada ejemplo
- [x] 6.7 Ejecutar `uv run pytest` y verificar que pasa sin API keys válidas

## 7. Documentación

- [x] 7.1 Reescribir `README.md` para la v1.0: qué hace el sistema y para quién, explicado sin dar por conocido el proyecto
- [x] 7.2 Explicar qué es CAG, por qué se usa aquí y qué se excluye deliberadamente (BD, retrieval, persistencia, caché)
- [x] 7.3 Documentar el flujo completo: recibir transcripción, inyectar contexto, llamar al LLM, devolver respuesta, indicando qué archivo hace cada paso
- [x] 7.4 Documentar setup con `uv`, tabla de variables de entorno y cómo elegir proveedor y modelo
- [x] 7.5 Añadir ejemplo `curl` del endpoint, la respuesta esperada, la ruta de Swagger y cómo ejecutar los tests

## 8. Verificación final

- [x] 8.1 Repasar el checklist de `docs/ejercicio.md` punto por punto
- [x] 8.2 Confirmar que no hay API keys ni secretos en código, tests, logs ni documentación
- [x] 8.3 Dejar preparado el comando de prueba real para que Javi lo ejecute; el agente no llama al LLM sin autorización explícita
