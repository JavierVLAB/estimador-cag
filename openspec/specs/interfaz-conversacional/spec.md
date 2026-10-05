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
La estimación SHALL mostrarse token a token mientras el modelo la genera, no de golpe al terminar.

#### Scenario: La respuesta se escribe en tiempo real
- **WHEN** el usuario envía una transcripción
- **THEN** la estimación se renderiza progresivamente a medida que el LLM emite texto

#### Scenario: La respuesta completa se guarda en el historial
- **WHEN** finaliza la generación de una estimación
- **THEN** el texto completo queda almacenado en el historial de la sesión y se re-renderiza en los siguientes ciclos de la interfaz

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

