## Why

El estimador actual deja demasiadas decisiones en una caja de chat libre y mantiene las instrucciones de la IA dentro del código. El módulo 04 necesita convertirlo en una herramienta guiada y permitir evolucionar sus instrucciones sin reescribir el servicio.

## What Changes

- Sustituir la entrada conversacional por un formulario de estimación con descripción, tipo de proyecto, nivel de detalle y formato de salida.
- Definir un contrato tipado para esa petición y devolver también la versión de prompt empleada.
- Mover las instrucciones, reglas condicionales y ejemplos a plantillas Jinja2 versionadas bajo `v1`.
- Adaptar el servicio y el endpoint `POST /api/v1/estimate` para construir por separado el mensaje de sistema y el mensaje de usuario y devolver la estimación completa al formulario.
- Añadir pruebas locales del contrato, del render de plantillas y del endpoint, además de documentar cómo usarlo.

## Capabilities

### New Capabilities

- `prompts-versionados`: Renderizar instrucciones de estimación desde plantillas Jinja2 versionadas con reglas dependientes del formato y el nivel de detalle.
- `formulario-estimacion`: Permitir que la interfaz recopile una petición de estimación guiada, la envíe al endpoint y muestre la respuesta completa.

### Modified Capabilities

- `estimacion-transcripcion`: Cambiar el contrato de estimación de una transcripción libre a una petición tipada y asociar la respuesta a la versión de prompt.
- `interfaz-conversacional`: Sustituir la entrada de chat por un formulario que use el endpoint HTTP de estimación y conserve las métricas disponibles de la respuesta.

## Impact

- Afecta a `streamlit_app.py`, el router de estimaciones, el servicio LLM y sus pruebas.
- Añade modelos de petición/respuesta, una dependencia Jinja2 y la carpeta `app/prompts/estimation/v1/`.
- No modifica proveedores, secretos, caché existente ni servicios externos; las pruebas seguirán sin usar red ni claves.
