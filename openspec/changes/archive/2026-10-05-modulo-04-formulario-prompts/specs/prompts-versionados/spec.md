## ADDED Requirements

### Requirement: Plantillas de estimación versionadas
El sistema SHALL guardar las instrucciones de estimación en `app/prompts/estimation/v1/` mediante `system.j2`, `user.j2` y `examples.j2`, en lugar de definirlas como un texto fijo dentro del servicio Python.

#### Scenario: La primera versión está disponible
- **WHEN** se solicita el render de estimación sin especificar una versión
- **THEN** el sistema usa las tres plantillas de `v1`

### Requirement: Render separado de mensajes
El cargador SHALL devolver un mensaje de sistema y un mensaje de usuario separados, con variables obligatorias y sin concatenarlos antes de llamar al proveedor.

#### Scenario: La descripción se renderiza como datos de usuario
- **WHEN** se renderiza una petición válida
- **THEN** la descripción aparece literalmente dentro de `<project_description>` en el mensaje de usuario
- **AND** no aparece en el mensaje de sistema

### Requirement: Reglas condicionales de estimación
La plantilla de sistema SHALL cambiar sus instrucciones según `output_format` y `detail_level`.

#### Scenario: Formato por fases
- **WHEN** `output_format` es `phases_table`
- **THEN** el mensaje de sistema incluye las instrucciones propias de una tabla por fases

#### Scenario: Nivel detallado
- **WHEN** `detail_level` es `detailed`
- **THEN** el mensaje de sistema exige listar supuestos por fase

#### Scenario: Nivel resumido
- **WHEN** `detail_level` es `summary`
- **THEN** el mensaje de sistema no incluye la instrucción de listar supuestos por fase

### Requirement: Detección de variables incorrectas
El entorno de plantillas SHALL fallar cuando una plantilla referencia una variable que no se ha proporcionado.

#### Scenario: Variable no definida
- **WHEN** una plantilla intenta usar una variable ausente
- **THEN** el render devuelve un error en lugar de producir texto incompleto
