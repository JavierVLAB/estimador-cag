# adjuntos Specification

## Purpose
TBD - created by archiving change memoria-conversacional-adjuntos. Update Purpose after archive.
## Requirements
### Requirement: Aceptación de adjuntos en la petición

El sistema SHALL aceptar adjuntos en la petición de estimación de una sesión mediante
`multipart/form-data`, junto a la transcripción y a los campos tipados de la estimación.

#### Scenario: Petición con adjuntos
- **WHEN** se envía una estimación de sesión con una transcripción, los campos tipados y uno o más archivos
- **THEN** el sistema procesa la transcripción y los adjuntos y devuelve la estimación

#### Scenario: Petición sin adjuntos
- **WHEN** se envía una estimación de sesión sin ningún archivo
- **THEN** el sistema se comporta igual que sin soporte de adjuntos, usando solo la transcripción

#### Scenario: Varios adjuntos
- **WHEN** se envían varios archivos en la misma petición
- **THEN** todos se procesan y sus textos llegan al prompt

### Requirement: Extracción local del texto

El sistema SHALL extraer el texto de los adjuntos localmente, sin subir el binario al
proveedor, y SHALL soportar documentos PDF y Word.

#### Scenario: PDF con texto extraíble
- **WHEN** se adjunta un PDF cuyo contenido es texto
- **THEN** el sistema extrae su texto y lo incorpora al contexto

#### Scenario: Word con texto extraíble
- **WHEN** se adjunta un documento Word
- **THEN** el sistema extrae sus párrafos y los incorpora al contexto

#### Scenario: PDF escaneado sin capa de texto
- **WHEN** se adjunta un PDF del que no se puede extraer texto
- **THEN** el sistema lo ignora sin fallar la estimación y deja constancia del motivo

### Requirement: Frontera explícita del material adjunto

El sistema SHALL delimitar cada bloque de texto extraído de modo que el modelo distinga
la transcripción de la documentación adjunta y de qué archivo procede cada bloque.

#### Scenario: La transcripción queda separada de los adjuntos
- **WHEN** hay al menos un adjunto con texto
- **THEN** el contexto enviado al proveedor contiene la transcripción y, después, un bloque por adjunto con el nombre del archivo y una marca de inicio y de fin

#### Scenario: Sin adjuntos no hay marcas
- **WHEN** no hay adjuntos con texto
- **THEN** el contexto enviado al proveedor es la transcripción sin marcas añadidas

### Requirement: Topes de tamaño de los adjuntos

El sistema SHALL acotar tanto el tamaño del archivo recibido como la cantidad de texto
que un adjunto puede aportar al contexto.

#### Scenario: Archivo por encima del tope de bytes
- **WHEN** un adjunto supera el tamaño máximo permitido por archivo
- **THEN** el sistema lo rechaza antes de leer su contenido y responde `413`, sin llamar al proveedor

#### Scenario: Texto extraído por encima del tope de caracteres
- **WHEN** el texto extraído de un adjunto supera el máximo de caracteres permitido
- **THEN** el sistema lo trunca al máximo, registra cuánto descartó y sigue con la estimación

#### Scenario: El límite de archivos por petición
- **WHEN** una petición incluye más adjuntos de los permitidos
- **THEN** el sistema la rechaza con `422`, sin leer los archivos

### Requirement: Fallos de adjuntos traducidos a errores HTTP

El sistema SHALL distinguir los fallos de adjuntos entre sí y SHALL traducirlos a códigos
HTTP distintos, sin exponer trazas internas.

#### Scenario: Extensión no soportada
- **WHEN** se adjunta un archivo de un tipo no soportado
- **THEN** el sistema responde `415` indicando el archivo rechazado

#### Scenario: Archivo corrupto
- **WHEN** un PDF o Word soportado no se puede leer
- **THEN** el sistema responde `422` indicando el archivo y el motivo

#### Scenario: Sin datos internos en el error
- **WHEN** se rechaza un adjunto
- **THEN** la respuesta no incluye la traza de la excepción ni credenciales

### Requirement: Configuración de los topes

La configuración del servicio SHALL establecer el tamaño máximo por archivo, el máximo de
caracteres extraídos por adjunto y el número máximo de adjuntos por petición.

#### Scenario: Topes desde la configuración
- **WHEN** se arranca el servicio
- **THEN** los tres topes provienen de la configuración y no de constantes en el código

