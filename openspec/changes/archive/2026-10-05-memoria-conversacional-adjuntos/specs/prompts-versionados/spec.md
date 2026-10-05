## ADDED Requirements

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