## ADDED Requirements

### Requirement: Techo de tamaño de la transcripción
El sistema SHALL rechazar transcripciones que superen `50_000` caracteres con un `422`, sin invocar al LLM.

#### Scenario: Transcripción demasiado larga
- **WHEN** se envía `transcription` con más de `50_000` caracteres
- **THEN** el sistema responde `422` sin llamar al proveedor LLM

### Requirement: Detección de respuesta truncada del LLM
El sistema SHALL tratar una respuesta del proveedor que haya sido cortada por el límite de tokens como un error del proveedor, no como una respuesta válida.

#### Scenario: OpenAI corta la respuesta
- **WHEN** `finish_reason` de la respuesta es `length`
- **THEN** el sistema responde `502` en lugar de devolver la estimación incompleta

#### Scenario: Anthropic corta la respuesta
- **WHEN** `stop_reason` de la respuesta es `max_tokens`
- **THEN** el sistema responde `502` en lugar de devolver la estimación incompleta

### Requirement: Respuesta vacía del LLM
El sistema SHALL rechazar una respuesta del proveedor vacía o sin contenido de texto como un error, en lugar de devolverla como una estimación válida.

#### Scenario: OpenAI devuelve contenido vacío
- **WHEN** el mensaje de respuesta de OpenAI es `None` o cadena vacía
- **THEN** el sistema responde `502`

#### Scenario: Anthropic devuelve sin bloques de texto
- **WHEN** la respuesta de Anthropic no contiene ningún bloque de tipo `text`
- **THEN** el sistema responde `502`

## MODIFIED Requirements

### Requirement: Errores del proveedor LLM
El sistema SHALL traducir los fallos de la llamada al proveedor LLM en una respuesta HTTP `502` con un mensaje claro, sin exponer trazas internas ni credenciales. Errores de programación propios (como `TypeError` o `KeyError`) NO se traducen a `502`: salen como errores internos (`500`).

#### Scenario: El proveedor falla
- **WHEN** la llamada al proveedor LLM lanza un error del SDK (red, autenticación, estado de la API)
- **THEN** el sistema responde `502` con un mensaje que indica que el proveedor no pudo generar la estimación
- **AND** el mensaje no contiene la API key ni la traza de la excepción

#### Scenario: Error propio del código
- **WHEN** la lógica del servicio falla por un error de programación no relacionado con el proveedor
- **THEN** el sistema responde `500`, no `502`