## Context

`POST /api/v1/estimate` devuelve actualmente `estimation`, `model` y `provider`. El servicio `llm_service.py` descarta el objeto `usage` de cada SDK al quedarse solo con el texto generado. El repositorio de referencia de la sesión usa `input_tokens` / `output_tokens` / `total_tokens`; el enunciado invita explícitamente a añadir campos útiles como «tokens utilizados».

## Goals / Non-Goals

**Goals:**

- Reportar en el response el consumo de tokens de cada llamada (entrada, salida, total), sin coste por llamada al LLM.
- Mantener la separación de capas: el servicio no conoce HTTP y el router solo formatea.
- Mantener la verificación con mocks (sin tráfico real).

**Non-Goals:**

- Calcular coste en EUR (depende de tarifas por modelo y proveedor, fuera del enunciado).
- Registrar el uso en logs o persistirlo (no hay persistencia por diseño CAG).
- Cambiar el modelo de respuesta o el `EstimationResult` más allá de añadir `usage`.

## Decisions

- **`TokenUsage` como dataclass propio en el servicio.** Un dataclass tipado en `llm_service.py` (`input_tokens`, `output_tokens`, `total_tokens`) protege el contrato y sigue el estilo de `EstimationResult`. Nombres en inglés por coherencia con el API y con el repo de referencia; comentarios en español.
- **Las funciones internas devuelven `tuple[str, TokenUsage]`.** `_generate_openai` y `_generate_anthropic` deben entregar el texto y el consumo juntos. Alternativa descartada: devolver solo el texto y leer `usage` en `generate_estimation` — obligaría a acoplar el texto al tipo de respuesta del SDK fuera de la función que hace la llamada.
- **`EstimationResult.usage: TokenUsage` como campo obligatorio.** La estimación sin consumo no existe; el router lo mapea directo a `EstimationResponse.usage`. Se descarta el tipo opcional.
- **OpenAI**: `input=usage.prompt_tokens`, `output=usage.completion_tokens`, `total=usage.total_tokens`. **Anthropic**: `input=usage.input_tokens`, `output=usage.output_tokens`, `total=input+output` (el SDK de Anthropic no reporta un total). Igual que el repo de referencia.
- **`EstimationResponse` gana un modelo Pydantic `TokenUsage`.** Int `Field(..., ge=0)` para que valores negativos del SDK se rechacen en el borde.

## Risks / Trade-offs

- Cambio aditivo del contrato → Mitigación: es un campo nuevo en el response; los consumidores que desechan campos desconocidos no se rompen, y solo suma información.
- Los dobles de SDK en los tests deben empezar a exponer `usage` → Mitigación: los helpers `_respuesta_openai` / `_respuesta_anthropic` se amplían con un `usage` ficticio y un test verifica el paso al response.
- Nombres de campo distintos entre SDK (OpenAI `prompt_tokens` vs Anthropic `input_tokens`) → Mitigación: la normalización ocurre dentro de cada `_generate_*`, que ya conoce su SDK.