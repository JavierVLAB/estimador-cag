# interfaz-conversacional

## Purpose

Exponer una interfaz conversacional web (Streamlit) sobre el estimador CAG que permita pegar transcripciones de reunión y ver la estimación token a token, sin curl, Postman ni Swagger.
## Requirements
### Requirement: Interfaz guiada de estimación
La aplicación SHALL exponer una interfaz Streamlit basada en formulario, donde el usuario describe el proyecto y selecciona su tipo, nivel de detalle y formato de salida antes de generar la estimación. El resultado y sus metadatos permanecerán visibles hasta la siguiente petición.

#### Scenario: El usuario envía una petición guiada
- **WHEN** el usuario completa una descripción válida y las tres opciones del formulario
- **THEN** la aplicación inicia una estimación usando los cuatro valores seleccionados

#### Scenario: El último resultado permanece visible
- **WHEN** se ha generado una estimación y el usuario no ha enviado una nueva petición
- **THEN** el texto de la estimación, su versión de prompt y sus métricas siguen visibles

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

### Requirement: Reutilización del system prompt CAG
La interfaz SHALL enviar el formulario a `POST /api/v1/estimate` y dejar que sea el backend quien renderice el prompt versionado, sin duplicar las instrucciones en el cliente.

#### Scenario: El prompt no diverge del endpoint
- **WHEN** la aplicación envía el formulario
- **THEN** el endpoint `POST /api/v1/estimate` renderiza el system prompt y el user prompt con el cargador y la versión activos

### Requirement: Configuración sin credenciales en el código
La API key SHALL leerse de la configuración (`app/config.py`, que carga `.env`) y nunca aparecer hardcodeada en el código de la aplicación.

#### Scenario: La clave se obtiene desde la configuración
- **WHEN** la aplicación realiza una llamada al LLM
- **THEN** la API key proviene de `settings` y no está escrita en el fichero fuente

### Requirement: Streaming en la capa de servicio
El servicio LLM SHALL ofrecer una función que produzca la respuesta del modelo en streaming (texto por fragmentos) para ambos proveedores soportados, reutilizando el prompt, el delimitador de transcripción y la configuración existentes. La función SHALL conservar el comportamiento ante respuestas truncadas (error, nunca texto incompleto como válido) y SHALL exponer el consumo de tokens de la llamada al terminar.

#### Scenario: OpenAI emite la respuesta en chunks
- **WHEN** el proveedor configurado es `openai` y se solicita streaming
- **THEN** la llamada usa `stream=True` y la función devuelve los fragmentos de texto del `delta.content` en orden

#### Scenario: Anthropic emite la respuesta en chunks
- **WHEN** el proveedor configurado es `anthropic` y se solicita streaming
- **THEN** la llamada usa el stream del SDK y la función devuelve los fragmentos de texto en orden

#### Scenario: Respuesta truncada en streaming
- **WHEN** el proveedor corta la generación por alcanzar el límite de tokens de salida
- **THEN** la función lanza el error de servicio correspondiente, sin entregar texto incompleto como estimación válida

#### Scenario: Consumo de tokens al terminar el stream
- **WHEN** el flujo de streaming se agota
- **THEN** el objeto devuelto expone los tokens de entrada, salida y totales de esa llamada

### Requirement: Panel lateral con contexto y métricas
La aplicación SHALL mantener en el panel lateral acceso de solo lectura al prompt activo y a los ejemplos de contexto, y SHALL mostrar las métricas de la última llamada.

#### Scenario: El panel muestra métricas de la última llamada
- **WHEN** se completa una estimación mediante el endpoint
- **THEN** el panel lateral muestra el modelo utilizado, los tokens de entrada, los tokens de salida y el tiempo de respuesta

### Requirement: El backend HTTP no cambia
La interfaz SHALL añadir la interfaz conversacional sin modificar el contrato del endpoint existente.

#### Scenario: El endpoint existente se mantiene
- **WHEN** se añade la aplicación Streamlit
- **THEN** `POST /api/v1/estimate` conserva su comportamiento, su respuesta y su código de la función de estimación no-streaming

### Requirement: El formulario usa el contrato HTTP del endpoint
La interfaz SHALL enviar el formulario como una petición JSON con los cuatro campos tipados del endpoint de estimación y SHALL mostrar la respuesta completa que este devuelva.

#### Scenario: El formulario envía el body tipado
- **WHEN** el usuario envía el formulario válido
- **THEN** la interfaz hace una petición `POST /api/v1/estimate` con `description`, `project_type`, `detail_level` y `output_format`

#### Scenario: La respuesta completa actualiza el resultado
- **WHEN** el endpoint devuelve una estimación correcta
- **THEN** el texto markdown devuelto queda visible como resultado del formulario

#### Scenario: Un fallo del endpoint se muestra sin filtrar el detalle interno
- **WHEN** la llamada al endpoint falla por un error de red o por un estado de error HTTP
- **THEN** la interfaz muestra un mensaje accionable y no la traza ni el cuerpo de la respuesta del backend

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

