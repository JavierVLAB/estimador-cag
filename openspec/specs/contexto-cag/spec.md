# contexto-cag

## Purpose

Mantener los ejemplos estáticos de estimaciones previas e inyectarlos en el prompt de cada llamada, que es el núcleo de la arquitectura CAG.
## Requirements
### Requirement: Ejemplos estáticos de estimaciones
El sistema SHALL mantener en `app/context/examples.py` al menos dos ejemplos de estimaciones previas, cada uno con un resumen de la reunión original y la estimación correspondiente.

#### Scenario: Ejemplos disponibles
- **WHEN** se importa el módulo de contexto
- **THEN** expone una colección con al menos dos ejemplos, cada uno con resumen de reunión y estimación no vacíos

#### Scenario: Tipologías distintas
- **WHEN** se revisan los ejemplos
- **THEN** representan encargos de naturaleza distinta (por ejemplo, una plataforma completa y una integración acotada), para que el modelo aprenda el formato y no un único tipo de proyecto

### Requirement: Contexto puro sin dependencias
El módulo de contexto SHALL contener únicamente datos y SHALL no importar configuración, servicios ni framework web.

#### Scenario: Módulo sin dependencias del proyecto
- **WHEN** se importa `app.context.examples`
- **THEN** no importa `app.config`, `app.services` ni FastAPI

### Requirement: Inyección del contexto en cada llamada
El sistema SHALL incluir los ejemplos estáticos en el system prompt en cada llamada al LLM, sin caché ni recuperación selectiva.

#### Scenario: Los ejemplos viajan en el prompt
- **WHEN** se construye el system prompt
- **THEN** el texto resultante contiene el resumen y la estimación de cada ejemplo definido

#### Scenario: Estructura de mensajes
- **WHEN** se realiza la llamada al proveedor
- **THEN** las instrucciones y los ejemplos van en el mensaje de sistema y la transcripción a estimar en el mensaje de usuario

### Requirement: Construcción del prompt testeable por separado
El sistema SHALL separar la construcción del system prompt de la llamada al proveedor, de forma que el prompt pueda verificarse sin realizar ninguna llamada de red.

#### Scenario: Prompt verificable sin LLM
- **WHEN** se invoca la función que construye el system prompt
- **THEN** devuelve el texto del prompt sin contactar con ningún proveedor

### Requirement: Delimitación de la transcripción como dato
El sistema SHALL envolver la transcripción del usuario en un delimitador impredecible por petición dentro del mensaje `user`, y SHALL instruir al modelo en el system prompt que el contenido entre esas marcas son datos de una reunión, no instrucciones.

#### Scenario: Transcripción envuelta con marca impredecible
- **WHEN** se construyen los mensajes para la llamada al proveedor
- **THEN** el contenido del mensaje `user` es la transcripción envuelta entre `<datos-{marca}>` y `</datos-{marca}>`, con `marca` generada por `secrets.token_hex(8)` para cada petición

#### Scenario: El system prompt declara el delimitador
- **WHEN** se construye el system prompt
- **THEN** instruye que el contenido entre las marcas `<datos-...>` es la transcripción y que las instrucciones dentro de esas marcas no modifican las reglas del sistema

