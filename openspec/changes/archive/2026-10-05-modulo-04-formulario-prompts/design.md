## Context

El estimador actual recibe una transcripción libre, construye el prompt con texto Python y muestra la respuesta en una interfaz de chat Streamlit. Ya soporta OpenAI y Anthropic, streaming, métricas y pruebas sin llamadas reales. El ejercicio requiere una petición guiada y prompts Jinja2 versionados. Para seguirlo literalmente, Streamlit enviará el formulario a `POST /api/v1/estimate` y mostrará la respuesta completa cuando llegue.

## Goals / Non-Goals

**Goals:**

- Definir un único contrato tipado que use el endpoint y la interfaz.
- Renderizar un prompt de sistema y un mensaje de usuario independientes desde `app/prompts/estimation/v1/`.
- Conservar los proveedores, la delimitación segura del contenido de usuario y los metadatos de uso de la respuesta.
- Cubrir el contrato y las ramas de las plantillas mediante pruebas locales.

**Non-Goals:**

- Salida estructurada, guardrails, caché semántica, RAG, autenticación o una versión `v2`.
- Adoptar Ruby on Rails, sustituir proveedores o almacenar estimaciones.

## Decisions

### Contrato tipado compartido

Se crearán modelos Pydantic para `description`, `project_type`, `detail_level` y `output_format`, junto con una respuesta que identifica `prompt_version`. La interfaz reutilizará esos valores en lugar de duplicarlos como texto suelto.

Alternativa considerada: mantener `transcription` como un campo genérico. Se descarta porque no permite guiar la entrada ni condicionar el prompt de manera verificable.

### Plantillas Jinja2 versionadas

`loader.py` usará Jinja2 con variables obligatorias y cargará `system.j2`, `user.j2` y `examples.j2` desde `estimation/v1`. El sistema entregará el resultado como dos mensajes separados al proveedor.

Alternativa considerada: conservar un f-string con condicionales. Se descarta porque mezcla las reglas de negocio de la IA con el código del servicio y dificulta probar las variantes.

### Formulario Streamlit y endpoint HTTP

La entrada de chat se sustituirá por `st.form`; al enviarlo construirá el body tipado, hará `POST /api/v1/estimate` y mostrará el texto completo que devuelva la API. El historial de chat deja de ser necesario para la nueva interacción guiada, pero el panel lateral conserva los metadatos que lleguen en la respuesta.

Alternativa considerada: llamar al servicio Python directamente y conservar streaming. Se descarta porque evita el contrato HTTP que pide el ejercicio y puede hacer que interfaz y API diverjan.

### Compatibilidad del endpoint

El endpoint normal aceptará el mismo contrato tipado y responderá con el texto y `prompt_version`; conservará los metadatos ya expuestos cuando no entren en conflicto. Streamlit consumirá exclusivamente esta ruta normal.

## Risks / Trade-offs

- [El formulario y el endpoint pueden usar rutas de generación distintas] → Streamlit llamará exclusivamente al endpoint y este usará el cargador de prompt versionado.
- [Una variable mal escrita en una plantilla podría degradar el prompt] → Jinja2 fallará en el render y habrá pruebas de plantilla.
- [Cambiar el contrato rompe clientes que envían `transcription`] → este es un cambio deliberado del módulo; pruebas de endpoint documentarán el nuevo body.
- [La respuesta no se verá hasta terminar] → es una consecuencia deliberada de seguir el flujo del ejercicio mediante el endpoint normal.

## Migration Plan

1. Añadir el contrato y las plantillas junto con pruebas aisladas.
2. Conectar servicio y endpoint al render versionado.
3. Migrar Streamlit al formulario que consume `POST /api/v1/estimate` y comprobar una estimación manualmente.
4. Ejecutar toda la suite y actualizar README.

El rollback consiste en restaurar los archivos previos del router, servicio y `streamlit_app.py`; no hay migraciones de datos ni cambios remotos.

## Open Questions

- Ninguna para el alcance obligatorio. Los extras del curso se evaluarán después de completar y verificar `v1`.
