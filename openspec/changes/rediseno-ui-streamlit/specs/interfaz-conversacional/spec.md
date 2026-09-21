## MODIFIED Requirements

### Requirement: Panel lateral con contexto y métricas
La aplicación SHALL exponer en el panel lateral acceso al system prompt activo (solo lectura) y al contexto estático inyectado (las estimaciones de ejemplo del CAG) mediante modales abiertos bajo demanda, y SHALL mostrar en el propio panel lateral las métricas de la última llamada (modelo utilizado, tokens de entrada, tokens de salida y tiempo de respuesta).

#### Scenario: El panel ofrece acceso al prompt y al contexto vía modal
- **WHEN** la aplicación se ejecuta
- **THEN** el panel lateral muestra un botón para abrir el system prompt activo en un modal y un botón para abrir las estimaciones de referencia del contexto CAG en otro modal, ambos en modo solo lectura

#### Scenario: El panel muestra métricas de la última llamada
- **WHEN** se completa una estimación en streaming
- **THEN** el panel lateral muestra el modelo utilizado, los tokens de entrada, los tokens de salida y el tiempo de respuesta de esa llamada
