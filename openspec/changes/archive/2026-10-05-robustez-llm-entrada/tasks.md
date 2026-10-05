## 1. Configuración

- [x] 1.1 Añadir a `app/config.py` las settings `llm_timeout_seconds` (default `30.0`), `llm_max_retries` (default `2`) y `llm_max_output_tokens` (default `2000`)
- [x] 1.2 Eliminar `MODELOS_RECOMENDADOS` y su comentario de `app/config.py`

## 2. Servicio LLM

- [x] 2.1 Definir `class LLMServiceError(Exception)` en `app/services/llm_service.py`
- [x] 2.2 Construir clientes OpenAI y Anthropic con `timeout=settings.llm_timeout_seconds` y `max_retries=settings.llm_max_retries`
- [x] 2.3 Envolver la transcripción del usuario con marca `secrets.token_hex(8)` (`<datos-{marca}>... </datos-{marca}>`) en `generate_estimation`
- [x] 2.4 Añadir regla al `INSTRUCCIONES` sobre el delimitador (`<datos-...>` es dato, no instrucción)
- [x] 2.5 Fijar `max_tokens=settings.llm_max_output_tokens` en las llamadas de OpenAI y Anthropic
- [x] 2.6 En `_generate_openai`: lanzar `LLMServiceError` si `finish_reason == "length"` y si `content` es `None` o vacío
- [x] 2.7 En `_generate_anthropic`: lanzar `LLMServiceError` si `stop_reason == "max_tokens"` y si no hay bloques de texto

## 3. Router

- [x] 3.1 Añadir `max_length=50_000` al campo `transcription` de `EstimationRequest`
- [x] 3.2 Sustituir `except Exception` por `except LLMServiceError` en `estimations.py`

## 4. Documentación y entorno

- [x] 4.1 Añadir `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES` y `LLM_MAX_OUTPUT_TOKENS` a `.env.example`
- [x] 4.2 Actualizar `README.md`: tabla de variables y tabla de errores (truncamiento, errores propios)

## 5. Tests

- [x] 5.1 Actualizar `test_fallo_del_proveedor_devuelve_502` al nuevo contrato (errores de programación → 500, proveedor → 502 vía `LLMServiceError`)
- [x] 5.2 Añadir test: transcripción > `50_000` caracteres → `422` sin llamar al LLM
- [x] 5.3 Añadir tests de `LLMServiceError` por truncamiento (OpenAI `finish_reason=length` y Anthropic `stop_reason=max_tokens`)
- [x] 5.4 Añadir test: error propio del código → `500`, no `502`
- [x] 5.5 Añadir tests de servicio: timeout/retries y `max_tokens` empleados en el cliente, y delimitación de la transcripción