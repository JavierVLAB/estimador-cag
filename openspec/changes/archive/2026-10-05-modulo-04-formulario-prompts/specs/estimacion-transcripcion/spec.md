## MODIFIED Requirements

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
