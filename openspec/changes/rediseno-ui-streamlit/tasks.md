## 1. Tema

- [x] 1.1 Crear `.streamlit/config.toml` con `[theme]`, `[theme.light]` y `[theme.dark]`: `primaryColor`, `backgroundColor`, `secondaryBackgroundColor`, `textColor`, `borderColor`, `font` (Inter), `codeFont` (JetBrains Mono), `baseRadius`, `showWidgetBorder`.
- [x] 1.2 Verificar contraste (WCAG AA) del `primaryColor` elegido contra texto blanco de botones, en ambos modos.

## 2. Layout y cabecera

- [x] 2.1 Cambiar `st.set_page_config` a `layout="wide"` y añadir `page_icon` Material Symbols.
- [x] 2.2 Añadir icono al `st.title` ("Estimador CAG").

## 3. Modales de referencia

- [x] 3.1 Crear función con `@st.dialog` para mostrar el system prompt activo (mismo contenido que hoy: `text_area` disabled).
- [x] 3.2 Crear función con `@st.dialog` para mostrar las estimaciones de referencia (mismo contenido que hoy: un bloque por ejemplo con `meeting_summary` y `estimation`).
- [x] 3.3 Sustituir los bloques fijos del sidebar por dos botones (con iconos) que abran cada modal.

## 4. Métricas

- [x] 4.1 Sustituir el bloque de `st.write` de métricas por métricas legibles de un vistazo. **Revisado tras feedback:** no se usó `st.metric` (fuente desproporcionada en un sidebar estrecho); se usó `st.caption` compacto dentro de `st.container(border=True)`, con las métricas tipadas en la dataclass `UltimaLlamada` en vez de un `dict`.
- [x] 4.2 Manejar el caso sin llamadas previas y el caso `usage=None` mostrando `"—"` en las métricas afectadas (helper `_o_guion`).

## 5. Detalles menores

- [x] 5.1 Añadir icono a `st.error` cuando falla la llamada al LLM.
- [x] 5.2 Revisar textos existentes (sentence casing) tras los cambios de layout.
- [x] 5.3 (añadido tras feedback) Nombre de cada ejemplo en el modal: campo `name: str` explícito en `EstimationExample` (`app/context/examples.py`), en vez de parsear el markdown de la estimación.
- [x] 5.4 (añadido tras feedback) Sección "Parámetros del proveedor" en el sidebar (modelo, proveedor, máx. tokens de salida, timeout, reintentos), leídos de `app/config.py`.
- [x] 5.5 (añadido tras feedback) `baseFontSize = 18` en `.streamlit/config.toml`; chat acotado con `st.columns([1, 4, 1])` en vez de `layout="centered"`; `st.rerun()` tras guardar métricas para que se vean en el mismo turno.

## 6. Verificación

- [x] 6.1 Ejecutar la app localmente (`streamlit run streamlit_app.py`) y probar: apertura de ambos modales, cambio de tema claro/oscuro, una estimación completa y un caso de error del proveedor LLM. Probado manualmente por Javi.
- [x] 6.2 Confirmar que la suite de tests completa sigue pasando — 24/24 tests OK (incluye la verificación tras añadir el campo `name` a `EstimationExample`, sin tests propios ya que no hay tests directos sobre ese módulo).
