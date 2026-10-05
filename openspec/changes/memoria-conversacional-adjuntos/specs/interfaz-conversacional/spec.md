## MODIFIED Requirements

### Requirement: Estimación en streaming

La estimación en streaming SHALL estar disponible en la capa de servicio, pero SHALL dejar
de ser un requisito de la interfaz: la interfaz basada en formulario entrega la estimación
completa al terminar la generación.

#### Scenario: El servicio sigue ofreciendo streaming
- **WHEN** se solicita una estimación en streaming al servicio
- **THEN** el servicio emite el texto por fragmentos y expone el consumo de tokens al agotarse el flujo

#### Scenario: La interfaz no muestra la estimación en streaming
- **WHEN** el usuario envía el formulario de una sesión
- **THEN** la estimación aparece completa una vez terminada la generación

## ADDED Requirements

### Requirement: La interfaz opera sobre una sesión

La interfaz SHALL crear una sesión al cargarse, SHALL enviar su identificador en cada
estimación posterior y SHALL mantener ese identificador mientras la conversación siga
viva.

#### Scenario: La sesión se crea al cargar
- **WHEN** se carga la interfaz
- **THEN** la aplicación solicita un `session_id` al backend y lo conserva

#### Scenario: Cada estimación viaja con su sesión
- **WHEN** el usuario envía el formulario
- **THEN** la estimación se envía al endpoint de la sesión activa

#### Scenario: Nueva conversación
- **WHEN** el usuario pulsa "Nueva conversación"
- **THEN** la aplicación solicita un `session_id` nuevo, descarta el resultado anterior y deja el panel de metadata vacío

### Requirement: La interfaz permite adjuntar documentación

La interfaz SHALL ofrecer un selector múltiple de archivos y SHALL enviarlos junto a la
transcripción en la petición de estimación.

#### Scenario: Selección de varios archivos
- **WHEN** el usuario selecciona uno o varios archivos y envía el formulario
- **THEN** la petición incluye esos archivos junto a la transcripción

#### Scenario: Ningún archivo seleccionado
- **WHEN** el usuario envía el formulario sin seleccionar archivos
- **THEN** la petición se envía sin adjuntos

### Requirement: La interfaz muestra el estado de la sesión

La interfaz SHALL mostrar el `project_metadata` actual y el número de turnos retenidos de
la sesión activa, y SHALL actualizarlos tras cada estimación.

#### Scenario: La metadata se ve tras cada turno
- **WHEN** se completa una estimación
- **THEN** el panel lateral refleja el `project_metadata` resultante de ese turno

#### Scenario: La memoria vacía se distingue de la ausente
- **WHEN** la sesión todavía no tiene hechos conocidos
- **THEN** el panel indica que todavía no se han deducido, en lugar de mostrar un error

### Requirement: Recuperación ante sesión perdida

La interfaz SHALL detectar que el backend ya no conoce la sesión activa y SHALL reponerse
creando una sesión nueva, sin dejar a la persona usuaria sin salida.

#### Scenario: La sesión dejó de existir
- **WHEN** una petición devuelve que la sesión no existe porque el backend se reinició
- **THEN** la interfaz lo comunica, crea una sesión nueva y permite reintentar la estimación

#### Scenario: No se pierde el texto introducido
- **WHEN** la sesión se repone por un reinicio del backend
- **THEN** la transcripción que la persona usuaria ya había escrito no se descarta sin aviso