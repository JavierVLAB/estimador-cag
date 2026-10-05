# estimacion-transcripcion

## Purpose

Exponer el endpoint que recibe la transcripción de una reunión y devuelve la estimación de software generada por el LLM.
## Requirements
### Requirement: Endpoint de estimación
El sistema SHALL exponer `POST /api/v1/estimate`, que recibe una petición JSON tipada con `description`, `project_type`, `detail_level` y `output_format`, y devuelve una estimación de software generada por el LLM junto con la versión del prompt usada.

#### Scenario: Estimación generada correctamente
- **WHEN** se envía un body JSON válido con los cuatro campos requeridos
- **THEN** el sistema responde `200` con el texto de estimación y `prompt_version` igual a la versión configurada en el servicio (`v1` por defecto)
- **AND** conserva los metadatos de modelo, proveedor y uso que no contradigan el nuevo contrato

#### Scenario: Campo obligatorio ausente
- **WHEN** el body no incluye uno de los cuatro campos requeridos
- **THEN** el sistema responde `422` con el detalle de validación, sin llamar al LLM

#### Scenario: Valor de opción inválido
- **WHEN** `project_type`, `detail_level` u `output_format` no contiene uno de los valores permitidos
- **THEN** el sistema responde `422`, sin llamar al LLM

#### Scenario: Descripción demasiado corta
- **WHEN** `description` tiene menos de 20 caracteres
- **THEN** el sistema responde `422`, sin llamar al LLM

### Requirement: Formato de la estimación
El sistema SHALL devolver la estimación como texto markdown libre, sin estructurar todavía las tareas en campos de salida, e identificará la versión de prompt que produjo el resultado.

#### Scenario: Respuesta en markdown
- **WHEN** el LLM devuelve una estimación
- **THEN** la respuesta contiene el texto markdown tal cual lo generó el modelo y `prompt_version` refleja la versión de plantilla empleada

### Requirement: Errores del proveedor LLM
El sistema SHALL traducir los fallos de la llamada al proveedor LLM en una respuesta HTTP `502` con un mensaje claro, sin exponer trazas internas ni credenciales.

#### Scenario: El proveedor falla
- **WHEN** la llamada al proveedor LLM lanza una excepción de servicio
- **THEN** el sistema responde `502` con un mensaje que indica que el proveedor no pudo generar la estimación
- **AND** el mensaje no contiene la API key ni la traza de la excepción

### Requirement: Separación de capas
El router SHALL ocuparse únicamente del transporte HTTP y el servicio LLM SHALL no depender de FastAPI; el servicio renderizará el prompt versionado antes de llamar al proveedor.

#### Scenario: El servicio es independiente de HTTP
- **WHEN** se importa `app.services.llm_service`
- **THEN** el módulo no importa FastAPI ni tipos de request/response HTTP

### Requirement: Metadatos de uso de tokens en la respuesta
El sistema SHALL conservar en la respuesta de `POST /api/v1/estimate` el consumo de tokens de la llamada al proveedor con `input_tokens`, `output_tokens` y `total_tokens` enteros no negativos.

#### Scenario: Consumo de tokens esperado en el response
- **WHEN** el proveedor devuelve una estimación con un consumo conocido
- **THEN** el campo `usage` del response refleja exactamente esos valores, sin redondeo ni cálculo de coste

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

### Requirement: Endpoint de estimación multi-turno

El sistema SHALL exponer `POST /api/v1/sessions/{session_id}/estimate`, que recibe
`multipart/form-data` con la transcripción, los tres campos tipados de la estimación y
adjuntos opcionales, y devuelve una estimación generada con el historial y la metadata de
esa sesión, junto con el estado de la sesión tras la llamada.

#### Scenario: Estimación en una sesión existente
- **WHEN** se envía una petición válida con un `session_id` existente
- **THEN** el sistema responde `200` con el texto de estimación, la versión de prompt, el consumo de tokens y el `project_metadata` resultante del turno

#### Scenario: La estimación respeta el contrato de salida
- **WHEN** el endpoint multi-turno devuelve una estimación
- **THEN** el formato de la respuesta coincide con el de `POST /api/v1/estimate`, más la metadata de la sesión

#### Scenario: Sesión inexistente
- **WHEN** el `session_id` no corresponde a ninguna sesión
- **THEN** el sistema responde `404` y no llama al proveedor

#### Scenario: Transcripción fuera de los límites
- **WHEN** la transcripción es más corta que el mínimo o más larga que el máximo admitidos
- **THEN** el sistema responde `422` sin llamar al proveedor

#### Scenario: El endpoint existente no cambia
- **WHEN** se usa `POST /api/v1/estimate`
- **THEN** conserva su contrato, su respuesta y su comportamiento, sin exigir `session_id`

### Requirement: La llamada al proveedor recibe el contexto de la sesión

El servicio de IA SHALL poder generar una estimación a partir de un historial de mensajes
y de un system prompt construidos por el llamador, sin construir él mismo el contexto.

#### Scenario: El servicio no conoce el modelo de sesiones
- **WHEN** se inspecciona el módulo de servicio LLM
- **THEN** no importa los tipos de sesión ni de historial

#### Scenario: El contexto lo decide el llamador
- **WHEN** el servicio genera una estimación multi-turno
- **THEN** usa el array de mensajes y el system prompt que le pasa quien lo invoca

