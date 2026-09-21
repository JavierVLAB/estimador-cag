## Why

El enunciado (ejercicio 03) pide una interfaz conversacional web sobre el estimador CAG para poder pegar transcripciones y ver la estimación en streaming sin curl, Postman ni Swagger. El backend actual solo expone HTTP, y el ejercicio además exige que el system prompt y el contexto sean exactamente los del endpoint CAG, con la API key gestionada desde `.env` y no hardcodeada.

## What Changes

- **Nuevo fichero `streamlit_app.py` en la raíz**: interfaz de chat (`st.chat_message`, `st.chat_input`) que envía la transcripción al LLM reutilizando `app/services/llm_service.py`, muestra la estimación en streaming con `st.write_stream` y mantiene el historial visible durante la sesión con `st.session_state`.
- **`app/services/llm_service.py`**: el servicio gana un generador `generate_estimation_stream` que devuelve la respuesta del modelo token a token (OpenAI: `stream=True` con `stream_options={"include_usage": True}`; Anthropic: `client.messages.stream()`). Reutiliza `build_system_prompt()`, `delimitar_transcripcion()` y la configuración existentes. Se conserva la función no-streaming actual.
- **Panel lateral (Nivel 3, opcional)**: `st.sidebar` que muestra el system prompt activo (solo lectura), las estimaciones de referencia del contexto CAG (desde `app/context/examples.py`) y métricas de la última llamada (modelo, tokens de entrada, tokens de salida, tiempo de respuesta). El `usage` de tokens se obtiene al final del stream; el tiempo se mide en el cliente.
- **Credenciales**: la API key, el proveedor y el modelo se leen desde `app.config.settings` (que ya carga `.env`), sin hardcodear nada ni introducir `st.secrets` como mecanismo paralelo.
- **Dependencia**: se añade `streamlit` a `pyproject.toml`.
- **Tests**: casos para el nuevo generador de streaming (doble de SDK): que itera los chunks en orden, que reutiliza el system prompt/delimitador, que lanza `LLMServiceError` si el stream de OpenAI se corta por `finish_reason="length"` o devuelve vacío, y que expone el `usage` final. Sin llamadas reales al LLM.

Sin cambios de arquitectura: sigue siendo CAG. El wrapper de abstracción, la caché y la trazabilidad son de la sesión en vivo, fuera del alcance de este ejercicio.

## Capabilities

### New Capabilities

- `interfaz-conversacional`: la interfaz Streamlit de chat sobre el estimador CAG.

### Modified Capabilities

- Ninguna. El endpoint HTTP no cambia; la nueva función de streaming es aditiva en la capa de servicio.

## Impact

- **Código**: `streamlit_app.py` (nuevo), `app/services/llm_service.py` (generador de streaming).
- **Tests**: `tests/test_llm_service.py` se amplía (nuevo fichero de pruebas opcional si la lógica del generador lo justifica).
- **Dependencias**: `streamlit` se añade a `pyproject.toml`; no se toca el `.env` real ni se añaden variables nuevas a `.env.example`.
- **Documentación**: `README.md` documenta cómo ejecutar la interfaz (`uv run streamlit run streamlit_app.py`).
- **Servicios externos**: no se tocan proveedores; la verificación se hace con mocks.