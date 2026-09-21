# estimacion-transcripcion

## Purpose

Exponer el endpoint que recibe la transcripción de una reunión y devuelve la estimación de software generada por el LLM.

## Requirements

### Requirement: Endpoint de estimación
El sistema SHALL exponer `POST /api/v1/estimate`, que recibe la transcripción de una reunión y devuelve la estimación de software generada por el LLM.

#### Scenario: Estimación generada correctamente
- **WHEN** se envía un body JSON con el campo `transcription` no vacío
- **THEN** el sistema responde `200` con un JSON que contiene `estimation` (texto markdown generado por el LLM), `model` (modelo utilizado) y `provider` (proveedor utilizado)

#### Scenario: Transcripción ausente
- **WHEN** el body no incluye el campo `transcription`
- **THEN** el sistema responde `422` con el detalle de validación de Pydantic, sin llamar al LLM

#### Scenario: Transcripción vacía o solo espacios
- **WHEN** `transcription` es una cadena vacía o compuesta únicamente de espacios
- **THEN** el sistema responde `422` y no llama al LLM

### Requirement: Formato de la estimación
El sistema SHALL devolver la estimación como texto markdown dentro de un campo string, sin estructurar las tareas en campos separados.

#### Scenario: Respuesta en markdown
- **WHEN** el LLM devuelve una estimación
- **THEN** el campo `estimation` contiene el texto markdown tal cual lo generó el modelo, sin post-procesar

### Requirement: Errores del proveedor LLM
El sistema SHALL traducir los fallos de la llamada al proveedor LLM en una respuesta HTTP `502` con un mensaje claro, sin exponer trazas internas ni credenciales.

#### Scenario: El proveedor falla
- **WHEN** la llamada al proveedor LLM lanza una excepción
- **THEN** el sistema responde `502` con un mensaje que indica que el proveedor no pudo generar la estimación
- **AND** el mensaje no contiene la API key ni la traza de la excepción

### Requirement: Separación de capas
El router SHALL ocuparse únicamente del transporte HTTP (validación de entrada, invocación del servicio y formato de salida), y el servicio LLM SHALL no depender de FastAPI.

#### Scenario: El servicio es independiente de HTTP
- **WHEN** se importa `app.services.llm_service`
- **THEN** el módulo no importa FastAPI ni tipos de request/response HTTP

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
