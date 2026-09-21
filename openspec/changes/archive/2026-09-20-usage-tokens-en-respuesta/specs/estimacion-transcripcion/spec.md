## ADDED Requirements

### Requirement: Metadatos de uso de tokens en la respuesta
El sistema SHALL devolver en la respuesta de `POST /api/v1/estimate` un campo `usage` con el consumo de tokens de la llamada al proveedor, con `input_tokens`, `output_tokens` y `total_tokens` enteros no negativos.

#### Scenario: Respuesta con consumo de tokens de OpenAI
- **WHEN** el proveedor es OpenAI y devuelve una estimación
- **THEN** el response `200` contiene `usage` con `input_tokens = usage.prompt_tokens`, `output_tokens = usage.completion_tokens` y `total_tokens = usage.total_tokens` de la llamada

#### Scenario: Respuesta con consumo de tokens de Anthropic
- **WHEN** el proveedor es Anthropic y devuelve una estimación
- **THEN** el response `200` contiene `usage` con `input_tokens = usage.input_tokens`, `output_tokens = usage.output_tokens` y `total_tokens = input_tokens + output_tokens`

#### Scenario: Consumo de tokens esperado en el response
- **WHEN** el proveedor devuelve una estimación con un consumo conocido
- **THEN** el campo `usage` del response refleja exactamente esos valores, sin redondeo ni cálculo de coste