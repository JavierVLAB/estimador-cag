## Why

La revisión del proyecto frente a `docs/revision_ejercicio_02.md` confirmó que el servicio arrastra seis de los fallos descritos: clientes LLM sin timeout ni reintentos explícitos, entrada sin techo de tamaño, respuesta truncada que se devuelve como si estuviera completa, un `except Exception` que maquilla bugs propios como fallos del proveedor, transcripción que entra al prompt sin frontera, y código muerto (`MODELOS_RECOMENDADOS`) con un docstring que promete un uso que no existe. Todos son fallos de frontera o de coste: el camino feliz funciona, los bordes no.

## What Changes

- **Nueva configuración** en `app/config.py`: `llm_timeout_seconds` (default `30.0`), `llm_max_retries` (default `2`) y `llm_max_output_tokens` (default `2000`). Eliminación de `MODELOS_RECOMENDADOS` (código muerto).
- **`app/services/llm_service.py`**: los clientes OpenAI y Anthropic se construyen con `timeout` y `max_retries` desde `Settings`. Se fija `max_tokens = llm_max_output_tokens` en ambas llamadas. Se añade una excepción de dominio `LLMServiceError`. La llamada a OpenAI lanza `LLMServiceError` si `finish_reason == "length"` (respuesta truncada) o si el contenido viene vacío; lo mismo en Anthropic con `stop_reason == "max_tokens"`. La transcripción del usuario viaja envuelta en un delimitador impredecible por petición (`<datos-{marca}>...</datos-{marca}>` con `marca = secrets.token_hex(8)`) y el system prompt explica que el contenido entre esas marcas son datos de una reunión, no instrucciones.
- **`app/routers/estimations.py`**: la transcripción gana `max_length=50_000`. El router captura solo `LLMServiceError` (502 con mensaje fijo); los errores propios (`TypeError`, `KeyError`, ...) ya no se tragan como `502` y salen como `500` de FastAPI.
- **Tests**: se actualizan los existentes al nuevo contrato y se añaden casos para entrada demasiado larga, respuesta truncada, respuesta vacía y que los bugs propios no se reporten como `502`.
- **`.env.example`** y **`README.md`**: documentan las variables nuevas.

Sin cambios de arquitectura: sigue siendo CAG, sin base de datos ni recuperación.

## Capabilities

### New Capabilities

Ninguna. El cambio modifica capacidades existentes.

### Modified Capabilities

- `estimacion-transcripcion`: se endurece el contrato del endpoint — techo de tamaño en la entrada, respuesta truncada tratada como error del proveedor, y error propio ya no se disfraza de `502`.
- `configuracion-proveedores`: nueva configuración de timeout, reintentos y tokens máximos de salida; eliminación de la constante muerta `MODELOS_RECOMENDADOS`.
- `contexto-cag`: la transcripción deja de viajar cruda — se delimita como dato por petición y el system prompt lo declara.

## Impact

- **Código**: `app/config.py`, `app/services/llm_service.py`, `app/routers/estimations.py`.
- **Tests**: `tests/*` se ajustan y amplían.
- **Configuración**: `.env.example` documenta `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, `LLM_MAX_OUTPUT_TOKENS` (sin valores reales). El `.env` real no se toca.
- **Documentación**: `README.md` (variables nuevas y comportamiento ante errores).
- **Fuera de alcance**: rediseño de la arquitectura CAG, base de datos, caché, recuperación, y el punto 11 de la revisión (derivar modelo del proveedor), que contradiría el enunciado: `LLM_MODEL` es variable independiente a propósito y los defaults actuales son coherentes.
- **Servicios externos**: no se tocan proveedores; la verificación se hace con mocks.