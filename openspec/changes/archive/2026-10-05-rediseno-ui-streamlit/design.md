## Context

`streamlit_app.py` reutiliza `build_system_prompt()` y `ESTIMATION_EXAMPLES` del backend (CAG) sin duplicarlos. El sidebar actual muestra siempre el system prompt completo (`text_area` de 320px) y un expander por cada ejemplo, antes de llegar a las métricas de la última llamada. No hay `.streamlit/config.toml`, así que la app usa el tema por defecto de Streamlit.

Este cambio es puramente de presentación: no toca `app/services/llm_service.py`, `app/context/examples.py` ni el contrato HTTP.

## Goals / Non-Goals

**Goals:**
- Sidebar compacto: solo botones de acceso + métricas.
- System prompt y ejemplos de referencia accesibles vía modal (`st.dialog`), sin perder que sean de solo lectura.
- Tema propio consistente (colores, tipografía, radios) definido en `config.toml`, con variantes light/dark.
- Métricas de la última llamada legibles de un vistazo (`st.metric` en fila) en vez de líneas de texto.

**Non-Goals:**
- No se cambia el streaming, el CAG, el prompt ni los ejemplos en sí.
- No se usa CSS custom (`st.html`/`unsafe_allow_html`) salvo que se pida explícitamente; toda la estética pasa por `config.toml`.
- No se introduce navegación multipágina ni autenticación.

## Decisions

- **Modal vía `st.dialog` en vez de expander**: `st.dialog` es el mecanismo nativo de Streamlit para contenido bajo demanda que no debe competir por espacio permanente en el sidebar. Alternativa descartada: mantener `expander` pero colapsado por defecto — se descarta porque el system prompt (320px) sigue empujando visualmente el resto del sidebar aunque esté colapsado un momento antes de abrirse inline.
- **Dos modales separados** (system prompt / ejemplos) en vez de uno combinado: mantiene cada uno enfocado y evita un modal largo con scroll interno doble.
- **Tema en `config.toml`, no CSS**: siguiendo la guía del proyecto (`developing-with-streamlit`), los colores y tipografía se definen de forma declarativa para sobrevivir a upgrades de Streamlit. Paleta "brand accent": `primaryColor` azul (`#0969DA` light / `#58A6FF` dark) sobre fondo neutro, con `Inter` (body/heading) y `JetBrains Mono` (código, para el system prompt).
- **`st.metric` en `st.container(horizontal=True)`** en vez de `st.write` por línea: da lectura tipo dashboard y es el patrón recomendado por la skill de Streamlit para KPIs cortos.
- **`layout="wide"`**: el chat gana ancho legible; no afecta a la lógica.

## Risks / Trade-offs

- [Los modales ocultan el system prompt por defecto, dificultando comparación visual rápida al depurar el prompt] → Mitigación: aceptable porque el prompt no cambia durante la sesión (es estático); el botón queda siempre visible en el sidebar.
- [Definir `[theme.light]` y `[theme.dark]` duplica algunos valores] → Mitigación: mantener la duplicación mínima, solo los tokens que realmente cambian entre modos.
- [`st.metric` con valores `None` cuando `usage` no está disponible] → Mitigación: mostrar `"—"` como valor cuando el dato no exista, igual que hace hoy la rama `if ultima` para el caso sin llamadas.

## Estado final (tras iteración con feedback visual)

Varias decisiones de esta sección se revisaron después de probar la primera versión. El estado realmente implementado es:

- **Layout**: `layout="wide"` se mantiene, pero el título, el caption y el chat viven dentro de `st.columns([1, 4, 1])`, acotando el ancho de lectura del chat sin volver a `layout="centered"` (que dejaba el chat demasiado estrecho).
- **Métricas de la última llamada**: se descartó `st.metric` — en un sidebar estrecho el tamaño de fuente de `st.metric` resultaba desproporcionado. Se sustituyó por `st.caption` compacto dentro de `st.container(border=True)`, y las métricas se tipan en una dataclass `UltimaLlamada` (en `streamlit_app.py`) en vez de un `dict` suelto, siguiendo el mismo patrón de tipado que ya usa `llm_service.py`.
- **Nombre de cada ejemplo en el modal**: en vez de parsear el encabezado markdown de `ejemplo.estimation` para deducir un título (frágil: dependía del formato exacto del texto), se añadió un campo `name: str` explícito a `EstimationExample` (`app/context/examples.py`), con el valor escrito a mano para cada ejemplo.
- **Nueva sección "Parámetros del proveedor"**: se añadió en el sidebar, no prevista en el diseño original, mostrando `llm_provider`, `llm_model`, `llm_max_output_tokens`, `llm_timeout_seconds` y `llm_max_retries` desde `app/config.py`. Se muestra también que la temperatura no se fija explícitamente (usa el default del SDK), en vez de inventar un valor.
- **Tipografía**: se añadió `baseFontSize = 18` en `.streamlit/config.toml` (no estaba en el diseño original) tras feedback de que el tamaño de fuente por defecto se veía pequeño en toda la app.
- **`st.rerun()` tras guardar métricas**: no estaba en el diseño original. Es necesario porque el sidebar se renderiza al principio del script run, antes de que termine el streaming; sin el rerun explícito, las métricas de una llamada solo se verían en el siguiente turno del usuario.
- **No implementado** (evaluado y descartado por requerir CSS fuera del alcance de "no CSS salvo pedido explícito"): título fijo (sticky) al hacer scroll, y límite máximo de líneas visibles en `st.chat_input` (el parámetro `height` solo fija un mínimo, no un máximo).
