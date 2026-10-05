## MODIFIED Requirements

### Requirement: Interfaz de chat con historial persistente
La aplicación SHALL exponer una interfaz Streamlit basada en formulario, donde el usuario describe el proyecto y selecciona su tipo, nivel de detalle y formato de salida antes de generar la estimación. El resultado y sus metadatos permanecerán visibles hasta la siguiente petición.

#### Scenario: El usuario envía una petición guiada
- **WHEN** el usuario completa una descripción válida y las tres opciones del formulario
- **THEN** la aplicación inicia una estimación usando los cuatro valores seleccionados

#### Scenario: El último resultado permanece visible
- **WHEN** se ha generado una estimación y el usuario no ha enviado una nueva petición
- **THEN** el texto de la estimación, su versión de prompt y sus métricas siguen visibles

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

### Requirement: Panel lateral con contexto y métricas
La aplicación SHALL mantener en el panel lateral acceso de solo lectura al prompt activo y a los ejemplos de contexto, y SHALL mostrar las métricas de la última llamada.

#### Scenario: El panel muestra métricas de la última llamada
- **WHEN** se completa una estimación mediante el endpoint
- **THEN** el panel lateral muestra el modelo utilizado, los tokens de entrada, los tokens de salida y el tiempo de respuesta

## ADDED Requirements

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