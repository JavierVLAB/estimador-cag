## 1. Servicio LLM

- [x] 1.1 Definir `TokenUsage` como dataclass en `app/services/llm_service.py` (`input_tokens`, `output_tokens`, `total_tokens`)
- [x] 1.2 Cambiar `_generate_openai` a devolver `tuple[str, TokenUsage]` normalizando `usage.prompt_tokens` / `usage.completion_tokens` / `usage.total_tokens`
- [x] 1.3 Cambiar `_generate_anthropic` a devolver `tuple[str, TokenUsage]` con `total = input + output`
- [x] 1.4 Añadir `usage: TokenUsage` (obligatorio) a `EstimationResult` y poblarlo en `generate_estimation`

## 2. Router

- [x] 2.1 Definir modelo Pydantic `TokenUsage` con campos `int` no negativos en `app/routers/estimations.py`
- [x] 2.2 Añadir campo `usage: TokenUsage` a `EstimationResponse` y mapearlo desde `EstimationResult`

## 3. Tests

- [x] 3.1 Ampliar `_respuesta_openai` y `_respuesta_anthropic` con `usage` ficticio
- [x] 3.2 Actualizar `EstimationResult` construidos en tests con `usage` de ejemplo
- [x] 3.3 Añadir test de confirmar `usage` valores llegan al response del endpoint
- [x] 3.4 Verificar `uv run pytest` pasa sin API keys ni tráfico real