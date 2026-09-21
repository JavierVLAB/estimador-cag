# interfaz-conversacional

## Purpose

Exponer una interfaz conversacional web (Streamlit) sobre el estimador CAG que permita pegar transcripciones de reunión y ver la estimación token a token, sin curl, Postman ni Swagger.

## Requirements

### Requirement: Interfaz de chat con historial persistente
La aplicación SHALL exponer una interfaz de chat (Streamlit) donde el usuario pueda escribir o pegar la transcripción de una reunión y ver la estimación del modelo como mensaje del asistente. El historial de la conversación SHALL permanecer visible durante toda la sesión.

#### Scenario: El usuario envía una transcripción
- **WHEN** el usuario escribe o pega una transcripción en el input de chat
- **THEN** la transcripción aparece como mensaje del usuario y la estimación resultante como mensaje del asistente

#### Scenario: El historial se conserva entre interacciones
- **WHEN** el usuario hace varias preguntas seguidas
- **THEN** todos los mensajes anteriores del usuario y del asistente siguen visibles en pantalla

### Requirement: Estimación en streaming
La estimación SHALL mostrarse token a token mientras el modelo la genera, no de golpe al terminar.

#### Scenario: La respuesta se escribe en tiempo real
- **WHEN** el usuario envía una transcripción
- **THEN** la estimación se renderiza progresivamente a medida que el LLM emite texto

#### Scenario: La respuesta completa se guarda en el historial
- **WHEN** finaliza la generación de una estimación
- **THEN** el texto completo queda almacenado en el historial de la sesión y se re-renderiza en los siguientes ciclos de la interfaz

### Requirement: Reutilización del system prompt CAG
La interfaz SHALL usar exactamente el mismo system prompt que el endpoint CAG del backend.

#### Scenario: El prompt no diverge del endpoint
- **WHEN** la aplicación construye la petición al LLM
- **THEN** el system prompt se obtiene de la misma función (`build_system_prompt`) y con los mismos ejemplos de contexto que usa `POST /api/v1/estimate`

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
La aplicación SHALL exponer en el panel lateral acceso al system prompt activo (solo lectura) y al contexto estático inyectado (las estimaciones de ejemplo del CAG) mediante modales abiertos bajo demanda, y SHALL mostrar en el propio panel lateral las métricas de la última llamada (modelo utilizado, tokens de entrada, tokens de salida y tiempo de respuesta).

#### Scenario: El panel ofrece acceso al prompt y al contexto vía modal
- **WHEN** la aplicación se ejecuta
- **THEN** el panel lateral muestra un botón para abrir el system prompt activo en un modal y un botón para abrir las estimaciones de referencia del contexto CAG en otro modal, ambos en modo solo lectura

#### Scenario: El panel muestra métricas de la última llamada
- **WHEN** se completa una estimación en streaming
- **THEN** el panel lateral muestra el modelo utilizado, los tokens de entrada, los tokens de salida y el tiempo de respuesta de esa llamada

### Requirement: El backend HTTP no cambia
La interfaz SHALL añadir la interfaz conversacional sin modificar el contrato del endpoint existente.

#### Scenario: El endpoint existente se mantiene
- **WHEN** se añade la aplicación Streamlit
- **THEN** `POST /api/v1/estimate` conserva su comportamiento, su respuesta y su código de la función de estimación no-streaming