## Why

La interfaz Streamlit actual (`streamlit_app.py`) no tiene tema propio (colores por defecto de Streamlit), y el sidebar muestra siempre el system prompt completo y todos los ejemplos de referencia, lo que lo satura y obliga a scrollear para llegar a las métricas. Es una revisión de diseño visual pura, sin tocar el CAG ni el contrato del backend.

## What Changes

- Mover el system prompt activo y las estimaciones de referencia del sidebar a modales (`st.dialog`), accesibles desde botones en el sidebar.
- Definir un tema propio en `.streamlit/config.toml`: colores (`primaryColor`, fondos, bordes), tipografía (`Inter` para body/heading, `JetBrains Mono` para código), `baseRadius`, `showWidgetBorder`, con variantes `[theme.light]` y `[theme.dark]`.
- `st.set_page_config(layout="wide", page_icon=...)` para dar más aire horizontal al chat.
- Iconos Material Symbols en el título, botones del sidebar y mensajes de error.
- Sustituir el bloque de métricas de la última llamada (texto plano con `st.write`) por `st.metric` en fila (`st.container(horizontal=True)`).

Sin cambios en `app/services/llm_service.py`, `app/context/examples.py`, `app/config.py` ni en ningún endpoint HTTP.

## Capabilities

### New Capabilities

(ninguna)

### Modified Capabilities

- `interfaz-conversacional`: el requirement "Panel lateral con contexto y métricas" cambia — el system prompt y las estimaciones de referencia dejan de mostrarse siempre visibles en el panel lateral y pasan a un modal abierto bajo demanda desde un botón del sidebar; siguen siendo de solo lectura y con el mismo contenido. Las métricas de la última llamada se mantienen en el sidebar pero como `st.metric` en vez de texto plano.

## Impact

- `streamlit_app.py`: reestructuración de la UI (sidebar, modales, layout, título, métricas). Sin cambios de lógica de negocio.
- `.streamlit/config.toml`: archivo nuevo, solo configuración de tema.
- `openspec/specs/interfaz-conversacional/spec.md`: actualización del requirement de panel lateral.
