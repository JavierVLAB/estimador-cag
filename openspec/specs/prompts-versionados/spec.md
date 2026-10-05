# prompts-versionados Specification

## Purpose
TBD - created by archiving change modulo-04-formulario-prompts. Update Purpose after archive.
## Requirements
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

### Requirement: Plantillas de la versión `v3`

El sistema SHALL mantener una versión `v3` de las plantillas de estimación que reciba el
`project_metadata` de la sesión y lo exponga al modelo en un bloque delimitado dentro del
system prompt, presente también cuando la metadata esté vacía.

#### Scenario: La versión `v3` está disponible
- **WHEN** se selecciona la versión `v3`
- **THEN** el sistema usa las plantillas de `estimation/v3`

#### Scenario: El bloque de metadata aparece siempre
- **WHEN** se renderiza la versión `v3` con cualquier estado de la metadata
- **THEN** el system prompt contiene un bloque `<project_metadata>` delimitado

#### Scenario: El bloque refleja los hechos conocidos
- **WHEN** la metadata contiene nombre de proyecto y tecnologías
- **THEN** el bloque `<project_metadata>` incluye esos valores

#### Scenario: La versión se puede seleccionar
- **WHEN** la configuración fija la versión de prompt en `v3`
- **THEN** el servicio renderiza y devuelve esa versión

### Requirement: Plantillas propias para la extracción de metadata

El sistema SHALL mantener una familia de plantillas versionadas, separada de las de
estimación, para instruir al modelo sobre cómo extraer el `project_metadata` de un turno.

#### Scenario: Familia de plantillas separada
- **WHEN** se renderiza la extracción de metadata
- **THEN** el sistema usa las plantillas de `metadata_extraction/` y no las de `estimation/`

#### Scenario: Las instrucciones piden null antes que suposiciones
- **WHEN** se renderiza el prompt del extractor
- **THEN** sus instrucciones indican que se devuelva `null` ante la duda, en lugar de un valor supuesto

#### Scenario: Solo devuelve hechos presentes
- **WHEN** se renderiza el prompt del extractor
- **THEN** sus instrucciones prohíben inventar hechos que no aparezcan en el turno

