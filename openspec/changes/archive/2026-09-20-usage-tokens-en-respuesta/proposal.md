## Why

El enunciado permite añadir campos útiles al response («tokens utilizados, coste estimado, timestamp, etc.») y la respuesta actual no revela el coste de la llamada: con `usage` el cliente sabe cuántos tokens consume cada estimación sin instrumentación externa. Es lo único del repositorio de referencia de la sesión 2 que aporta valor real y no está en nuestro proyecto.

## What Changes

- **`app/services/llm_service.py`**: el resultado de una estimación gana un dataclass `TokenUsage` (con `input_tokens`, `output_tokens` y `total_tokens`). El flujo interno ya no devuelve solo texto: `_generate_openai` y `_generate_anthropic` devuelven el texto y el consumo que reporta cada SDK (OpenAI: `usage.prompt_tokens` / `usage.completion_tokens`; Anthropic: `usage.input_tokens` / `usage.output_tokens`, total = suma). `EstimationResult` incorpora el campo `usage`.
- **`app/routers/estimations.py`**: `EstimationResponse` gana un modelo Pydantic `TokenUsage` y un campo `usage` (obligatorio), reflejando el consumo de la llamada.
- **Tests**: los dobles de SDK incluyen `usage` ficticio y se actualizan las instancias de `EstimationResult`; se añade un caso que verifica que `usage` llega al response con los valores del proveedor.

Sin cambios de arquitectura: sigue siendo CAG. No hay llamadas reales al LLM en la verificación.

## Capabilities

### New Capabilities

Ninguna. El cambio modifica una capacidad existente.

### Modified Capabilities

- `estimacion-transcripcion`: la respuesta `200` del endpoint gana el campo `usage` (tokens de entrada, salida y total de la llamada al proveedor).

## Impact

- **Código**: `app/services/llm_service.py`, `app/routers/estimations.py`.
- **Tests**: `tests/test_llm_service.py` y `tests/test_estimations.py` se ajustan y amplían.
- **API**: la respuesta de `POST /api/v1/estimate` incluye un objeto `usage`; es un cambio aditivo, no rompe consumidores existentes.
- **Configuración**: ninguna. El coste en EUR no se calcula; solo se reporta consumo de tokens.
- **Servicios externos**: no se tocan proveedores; la verificación se hace con mocks.