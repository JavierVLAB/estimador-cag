## 1. Dependencia

- [x] 1.1 Añadir `streamlit` a `pyproject.toml` y sincronizar con `uv sync`

## 2. Servicio LLM: streaming

- [x] 2.1 Introducir en `app/services/llm_service.py` un objeto iterable (p. ej. `EstimationStream`) que devuelve chunks de texto y expone `model`, `provider` y `usage` al agotarse
- [x] 2.2 Implementar `_generate_openai_stream(system_prompt, contenido_usuario)` con `stream=True` y `stream_options={"include_usage": True}`, produciendo solo `delta.content` no vacío y volcando el `usage` final en el objeto iterable
- [x] 2.3 Lanzar `LLMServiceError` en streaming si OpenAI termina con `finish_reason="length"` (respuesta truncada) o sin texto
- [x] 2.4 Implementar `_generate_anthropic_stream(system_prompt, contenido_usuario)` con `client.messages.stream()`, iterando `stream.text_stream` y leyendo `get_final_message()` para `stop_reason` y `usage`
- [x] 2.5 Lanzar `LLMServiceError` en streaming si Anthropic termina con `stop_reason="max_tokens"` o sin texto
- [x] 2.6 Implementar `generate_estimation_stream(transcription)` que reutilice `build_system_prompt()`, `delimitar_transcripcion()` y `settings`, despachando al proveedor configurado y conservando intacta la función no-streaming `generate_estimation`
- [x] 2.7 Documentar las funciones nuevas con docstring y comentarios en español (el "por qué")

## 3. Aplicación Streamlit

- [x] 3.1 Crear `streamlit_app.py` en la raíz con inicialización del historial en `st.session_state` y render de los mensajes existentes (`st.chat_message`)
- [x] 3.2 Aceptar la transcripción con `st.chat_input`, mostrarla como mensaje de usuario y llamar a `generate_estimation_stream`
- [x] 3.3 Renderizar la estimación con `st.write_stream` y guardar la respuesta completa en el historial; capturar `LLMServiceError` mostrando `st.error` sin guardar respuesta fallida
- [x] 3.4 Medir el tiempo de la llamada con `time.perf_counter()` y guardar métricas (modelo, tokens in/out, tiempo) en `st.session_state`
- [x] 3.5 Añadir `st.sidebar` con el system prompt activo (solo lectura), las estimaciones de referencia de `app/context/examples.py` y las métricas de la última llamada
- [x] 3.6 Importar credenciales, proveedor y modelo desde `app.config.settings` (sin keys hardcodeadas ni `st.secrets` paralelo)

## 4. Tests

- [x] 4.1 Añadir tests del streaming con dobles de SDK: orden de chunks en OpenAI y Anthropic
- [x] 4.2 Test de que `generate_estimation_stream` reutiliza el system prompt y el delimitador de transcripción
- [x] 4.3 Tests de truncamiento y respuesta vacía en streaming (ambos proveedores) lanzando `LLMServiceError`
- [x] 4.4 Test de que el `usage` final queda expuesto en el objeto iterable tras agotarse el stream
- [x] 4.5 Test de que la función no-streaming `generate_estimation` sigue verificando sus casos existentes sin cambios

## 5. Documentación y verificación

- [x] 5.1 Añadir a `README.md` una sección con el comando `uv run streamlit run streamlit_app.py` y aclarar que la interfaz reutiliza el mismo CAG del backend
- [x] 5.2 Verificar que `uv run pytest` pasa sin API keys ni tráfico real
- [x] 5.3 Confirmar que el contrato de `POST /api/v1/estimate` no ha cambiado