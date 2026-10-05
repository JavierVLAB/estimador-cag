# Memoria conversacional

## Purpose

Permitir que el estimador recuerde sobre qué proyecto se está hablando a lo largo de
varios turnos dentro de una sesión, separando el historial conversacional —lo que se
dijo— del conocimiento del proyecto —lo que se sabe de él—.

## ADDED Requirements

### Requirement: Ciclo de vida de una sesión

El sistema SHALL crear sesiones bajo demanda y mantenerlas en memoria del proceso,
indexadas por un identificador, y SHALL exponerlas por HTTP para poder crearlas e
inspeccionarlas.

#### Scenario: Crear una sesión
- **WHEN** se envía `POST /api/v1/sessions`
- **THEN** el sistema responde `201` con un `session_id` que es un UUID v4
- **AND** la sesión existe y empieza con historial vacío y metadata vacía

#### Scenario: Identificadores únicos
- **WHEN** se crean dos sesiones
- **THEN** sus `session_id` son distintos

#### Scenario: Inspeccionar una sesión
- **WHEN** se envía `GET /api/v1/sessions/{session_id}` con un identificador existente
- **THEN** el sistema responde `200` con el `project_metadata` actual, el número de mensajes retenidos y el límite de turnos configurado

#### Scenario: Sesión inexistente
- **WHEN** se consulta o se estima sobre un `session_id` que no está en el diccionario
- **THEN** el sistema responde `404` con un motivo identificable, sin crear la sesión implícitamente

#### Scenario: El estado es volátil
- **WHEN** el proceso se reinicia
- **THEN** las sesiones existentes se pierden y sus identificadores dejan de ser válidos

### Requirement: Historial con ventana deslizante

El sistema SHALL conservar los últimos `session_max_turns` pares de mensaje
usuario/asistente de cada sesión, y SHALL descartar los pares más antiguos al superar
ese límite.

#### Scenario: Un turno son dos mensajes
- **WHEN** una estimación se completa
- **THEN** el historial incorpora un mensaje de usuario con la transcripción y uno de asistente con la estimación

#### Scenario: La ventana respeta el límite
- **WHEN** una sesión acumula más turnos que `session_max_turns`
- **THEN** el historial conserva exactamente los últimos `session_max_turns` pares y ha descartado el resto

#### Scenario: El recorte conserva la alternancia de roles
- **WHEN** se descartan mensajes por superar el límite
- **THEN** el número de mensajes descartados es par, de modo que el historial resultante no empieza por un mensaje de asistente

#### Scenario: El límite es configurable
- **WHEN** se cambia `session_max_turns` en la configuración
- **THEN** las sesiones creadas después usan ese límite

### Requirement: El system prompt se deriva de la metadata, no del historial

El sistema SHALL mantener el system prompt fuera del historial y SHALL re-renderizarlo en
cada turno a partir del `project_metadata` vigente, de modo que un cambio en los hechos
conocidos se refleje en la siguiente llamada sin reescribir el historial.

#### Scenario: La metadata alcanza al prompt
- **WHEN** el `project_metadata` de la sesión contiene un nombre de proyecto
- **THEN** el system prompt enviado al proveedor incluye ese nombre

#### Scenario: El historial no contiene el system prompt
- **WHEN** se inspecciona el historial de una sesión
- **THEN** sus mensajes son solo de rol usuario y asistente, sin mensajes de sistema

### Requirement: `project_metadata` separada del historial

El sistema SHALL mantener los hechos conocidos del proyecto en curso —nombre del
proyecto, tamaño de equipo asumido, tecnologías mencionadas y alcance acordado— en una
estructura distinta del historial, y SHALL combinarla con la metadata anterior según
unas reglas de fusión explícitas.

#### Scenario: Primer turno sin metadata
- **WHEN** se genera una estimación en una sesión recién creada
- **THEN** la metadata resultante es válida y se considera vacía si no se dedujo ningún hecho

#### Scenario: Un hecho corrige un escalar
- **WHEN** la metadata nueva trae un nombre de proyecto distinto del anterior
- **THEN** la metadata combinada adopta el nuevo valor

#### Scenario: Un hecho ausente preserva el valor anterior
- **WHEN** la metadata nueva deja el tamaño de equipo sin definir
- **THEN** la metadata combinada conserva el tamaño de equipo que ya se conocía

#### Scenario: Las tecnologías se acumulan sin duplicar
- **WHEN** la metadata nueva incluye tecnologías ya conocidas con distinta capitalización
- **THEN** la metadata combinada contiene cada tecnología una sola vez

#### Scenario: La metadata es inyectable en el prompt
- **WHEN** el system prompt se renderiza con una metadata con hechos
- **THEN** el texto resultante contiene esos hechos dentro de un bloque `<project_metadata>` identificable

### Requirement: Extracción de la metadata tras cada turno

El sistema SHALL obtener el `project_metadata` de cada turno a partir de la interacción,
y SHALL mantener la estimación aunque esa extracción no tenga éxito.

#### Scenario: La extracción actualiza la metadata
- **WHEN** un turno aporta hechos nuevos sobre el proyecto
- **THEN** la metadata de la sesión queda actualizada antes de la siguiente petición

#### Scenario: Un fallo del extractor no rompe la estimación
- **WHEN** la extracción de metadata falla o devuelve un resultado no interpretable
- **THEN** el sistema responde con la estimación generada y conserva la metadata anterior

### Requirement: Concurrencia sobre una misma sesión

El sistema SHALL proteger el acceso al diccionario de sesiones para que dos peticiones
simultáneas sobre la misma sesión no puedan corromper su historial.

#### Scenario: Turnos simultáneos
- **WHEN** llegan dos peticiones concurrentes sobre la misma sesión
- **THEN** el historial resultante sigue respetando la alternancia de roles y el límite de turnos

### Requirement: Configuración de la sesión

La configuración del servicio SHALL establecer el número máximo de turnos por sesión y la
cantidad máxima de adjuntos por petición.

#### Scenario: Límites desde la configuración
- **WHEN** se arranca el servicio
- **THEN** el límite de turnos y el de adjuntos provienen de la configuración y no de constantes en el código