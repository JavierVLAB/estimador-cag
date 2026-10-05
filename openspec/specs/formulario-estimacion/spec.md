# formulario-estimacion Specification

## Purpose
TBD - created by archiving change modulo-04-formulario-prompts. Update Purpose after archive.
## Requirements
### Requirement: Formulario guiado de estimación
La interfaz Streamlit SHALL mostrar un formulario con una descripción del proyecto, tipo de proyecto, nivel de detalle y formato de salida.

#### Scenario: Usuario completa el formulario
- **WHEN** el usuario completa los cuatro campos y envía el formulario
- **THEN** la aplicación crea una petición de estimación con esos valores

### Requirement: Validación local de la descripción
La interfaz SHALL impedir el envío de una descripción con menos de 20 caracteres útiles y mostrará un mensaje claro.

#### Scenario: Descripción demasiado corta
- **WHEN** el usuario intenta enviar una descripción inferior al mínimo
- **THEN** la aplicación muestra el error y no inicia la generación

### Requirement: Envío al endpoint y resultado completo
La interfaz SHALL enviar la petición tipada a `POST /api/v1/estimate`, mostrar el texto completo devuelto por el endpoint y conservar en el panel lateral los metadatos disponibles de la última generación completada.

#### Scenario: Estimación completada
- **WHEN** el endpoint responde correctamente a una petición válida
- **THEN** la aplicación muestra el texto completo de la estimación
- **AND** actualiza modelo, proveedor, tokens y tiempo disponibles en el panel lateral

#### Scenario: Fallo durante la generación
- **WHEN** el endpoint devuelve un error de servicio o de red
- **THEN** la aplicación muestra un mensaje comprensible y no guarda una estimación incompleta como resultado válido

