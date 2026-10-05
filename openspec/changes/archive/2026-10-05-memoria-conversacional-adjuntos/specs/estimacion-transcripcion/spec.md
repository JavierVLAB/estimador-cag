## ADDED Requirements

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