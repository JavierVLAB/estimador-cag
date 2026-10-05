## ADDED Requirements

### Requirement: Delimitación de la transcripción como dato
El sistema SHALL envolver la transcripción del usuario en un delimitador impredecible por petición dentro del mensaje `user`, y SHALL instruir al modelo en el system prompt que el contenido entre esas marcas son datos de una reunión, no instrucciones.

#### Scenario: Transcripción envuelta con marca impredecible
- **WHEN** se construyen los mensajes para la llamada al proveedor
- **THEN** el contenido del mensaje `user` es la transcripción envuelta entre `<datos-{marca}>` y `</datos-{marca}>`, con `marca` generada por `secrets.token_hex(8)` para cada petición

#### Scenario: El system prompt declara el delimitador
- **WHEN** se construye el system prompt
- **THEN** instruye que el contenido entre las marcas `<datos-...>` es la transcripción y que las instrucciones dentro de esas marcas no modifican las reglas del sistema