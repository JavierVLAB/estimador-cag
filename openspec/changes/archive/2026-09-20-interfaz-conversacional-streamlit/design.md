## Context

El backend expone `POST /api/v1/estimate` con un endpoint CAG: el router valida la entrada y delega en `app/services/llm_service.generate_estimation()`, que construye el prompt con `build_system_prompt()` (instrucciones + ejemplos de `app/context/examples.py`), delimita la transcripción con `<datos-{marca}>` y llama al proveedor (OpenAI o Anthropic) de forma **no-streaming**: recibe la respuesta completa y devuelve un `EstimationResult`.

El ejercicio 03 pide una interfaz Streamlit en la raíz (`streamlit_app.py`) que permita pegar transcripciones, ver la estimación **token a token**, conservar el historial en la sesión y (Nivel 3) mostrar en un sidebar el prompt activo, el contexto CAG y métricas de la última llamada. El mismo system prompt y la misma configuración del endpoint deben reutilizarse; la API key no puede ir hardcodeada.

Restricciones del proyecto: capa de servicio sin dependencia de Streamlit ni FastAPI, configuración centralizada en `app/config.py`, arquitectura CAG intacta, y sin caché/wrapper/trazabilidad (eso es de la sesión en vivo).

## Goals / Non-Goals

**Goals:**

- `streamlit_app.py` en la raíz: chat con `st.chat_message` + `st.chat_input`, historial en `st.session_state`, streaming con `st.write_stream`.
- Capa de servicio con una función de streaming que reutilice `build_system_prompt()`, `delimitar_transcripcion()` y `Settings` (proveedor, modelo, keys, `llm_max_output_tokens`).
- Sidebar (Nivel 3): system prompt en solo lectura, contexto de referencia y métricas (modelo, tokens in/out, tiempo) de la última llamada.
- Tests del generador de streaming con dobles de SDK, sin llamadas reales.

**Non-Goals:**

- Wrapper de abstracción de proveedores, caché de respuestas y capa de logging/trazabilidad (sesión en vivo).
- Endpoint SSE o de streaming en FastAPI: la interfaz es Streamlit, que consume el servicio directamente.
- Enviar el historial de la conversación al modelo como contexto: cada estimación es independiente (CAG); el historial es solo visual.
- Cambios en el endpoint HTTP existente ni en su contrato.
- `st.secrets` / `.streamlit/secrets.toml` como mecanismo paralelo de configuración.

## Decisions

### 1. Streaming en la capa de servicio, no en el script
Se añade `generate_estimation_stream(transcription)` a `app/services/llm_service.py`. Devuelve un objeto iterable que produce **strings** (chunks de texto) y que, cuando se agota, expone `model`, `provider` y `usage` como atributos. Internamente se reutilizan `build_system_prompt()` y `delimitar_transcripcion()`.

**Por qué esta decisión:** el ejercicio pide explícitamente reutilizar la lógica del proyecto, y la separación por capas exige que el script no conozca los SDK. Alternativa considerada — llamar a OpenAI/Anthropic directamente desde `streamlit_app.py` con `st.secrets`— se descarta: duplicaría la construcción del prompt, la gestión de la key y el delimitador, y rompería `routers → services → context`.

Detalle de implementación: el objeto iterable (`EstimationStream`) recibe los generadores del proveedor por debajo; el generador, al terminar, vuelca el `TokenUsage` final en el objeto. El tipo lo hace directo para `st.write_stream` (acepta iterables de strings) y testable sin Streamlit.

### 2. `st.write_stream`, no placeholder manual
Se usa `st.write_stream(flujo)` sobre el objeto iterable, y se acumula el texto en una variable local para guardarlo en el historial al terminar.

**Por qué:** el material del módulo lo recomienda explícitamente para este ejercicio; Streamlit gestiona el render progresivo y el bucle de chunks. Alternativa considerada — patrón `placeholder.write(delta)`— aporta control fine-grained innecesario aquí.

### 3. Configuración vía `app.config.settings`, no `st.secrets`
El script importa `settings` desde `app/config.py`, que ya lee `.env` y expone `openai_api_key` / `anthropic_api_key`, `llm_provider`, `llm_model`. La key nunca se escribe en el código.

**Por qué:** hay una única fuente de configuración y el requisito «la API key se lee desde `.env`» se cumple sin duplicar mecanismos. `st.secrets` añadiría un segundo flujo (`.streamlit/secrets.toml`) que hay que mantener sincronizado. Si en el futuro se despliega en Streamlit Cloud, bastaría con poblar las mismas variables como secrets.

### 4. Historial solo visual, cada llamada independiente
`st.session_state.messages` guarda `{"role": "user"|"assistant", "content": ...}` y se usa únicamente para renderizar la conversación. Al enviar se pasa solo la transcripción nueva a `generate_estimation_stream`.

**Por qué:** el contrato del servicio (y del endpoint) recibe una transcripción y devuelve una estimación; reintroducir el historial como mensajes del modelo cambiaría la semántica del prompt y mezclaría instrucciones con datos. Cada transcripción es una estimación autónoma.

### 5. Truncamiento y usage en streaming
- OpenAI: `stream=True` con `stream_options={"include_usage": True}`. El último chunk trae `usage` con `delta` vacío; si `choices[0].finish_reason == "length"` se lanza `LLMServiceError` (mismo error que la llamada no-streaming). Se producen solo chunk con `delta.content` no vacío.
- Anthropic: `client.messages.stream()`; `for texto in stream.text_stream` y, al terminar, `stream.get_final_message()` para leer `stop_reason` (truncamiento) y `usage`.

**Por qué:** mantiene la paridad de comportamiento con `generate_estimation()` (respuesta truncada = error, nunca se entrega texto incompleto como válido) y aporta el `usage` que pide el Nivel 3. El tiempo de respuesta lo mide el script alrededor de la iteración con `time.perf_counter()`.

## Risks / Trade-offs

- [El error `LLMServiceError` se lanza a mitad de iteración] → El script envuelve el consumo del flujo en `try/except` y muestra `st.error`; el historial no guarda la respuesta fallida.
- [`include_usage` depende del SDK/proveedor] → El generador ignora chunks sin `delta.content`; los tests con dobles cubren el caso de chunk-fantasma con `usage`.
- [Streamlit es un framework que se ejecuta interactivamente; la UI no se cubre con pytest] → Se testea toda la lógica del servicio (el generador) y el script queda como una capa fina; la verificación de la interfaz es `streamlit run streamlit_app.py` (la ejecuta Javi, no el agente).
- [Ampliar `pyproject.toml`] → Dependencia de desarrollo/uso acotada a `streamlit`; se documenta en README; el backend FastAPI sigue siendo la API para consumidores no-Streanlit.

## Migration Plan

1. Añadir `streamlit` a `pyproject.toml` y `uv sync`.
2. Implementar el generador de streaming en el servicio con sus tests (mocks).
3. Crear `streamlit_app.py` (chat, sesión, sidebar).
4. Documentar en `README.md` la ejecución (`uv run streamlit run streamlit_app.py`).
5. Verificación: `uv run pytest` (sin tráfico real) y, en el entorno local de Javi, `streamlit run`.

Rollback: revertir el cambio o eliminar `streamlit_app.py`; el backend no se toca, así que el servicio HTTP queda intacto.

## Open Questions

Ninguna. La única decisión de alcance (incluir Nivel 3) se confirmó antes de proponer.