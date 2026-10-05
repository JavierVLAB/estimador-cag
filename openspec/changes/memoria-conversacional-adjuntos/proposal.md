# Memoria conversacional y adjuntos

## Why

El estimador es hoy transaccional: entra una transcripción, sale una estimación y no
queda nada. Eso funciona para "estima esto y olvídalo", pero no para lo que pasa en una
reunión real, donde el cliente refina el alcance, corrige un dato y vuelve a pedir
estimación del mismo proyecto. Cada turno pierde el contexto, y el modelo vuelve a
preguntar lo que ya se le dijo.

A la vez, la información que más cambia una estimación (una propuesta previa, una
especificación técnica) llega hoy por fuera y no entra al servicio.

## What Changes

- **Sesiones en memoria del proceso.** `POST /api/v1/sessions` crea una sesión y
  devuelve un `session_id` (UUID v4). El servicio mantiene un diccionario de sesiones
  que se pierde al reiniciar y no se comparte entre workers.
- **Endpoint multi-turno.** `POST /api/v1/sessions/{session_id}/estimate` acepta
  `multipart/form-data` con la transcripción, los tres campos tipados del formulario y
  adjuntos opcionales. Tras cada llamada actualiza el historial y la metadata de la
  sesión.
- **Historial con ventana deslizante.** Se conservan los últimos `session_max_turns`
  pares user/assistant. El recorte descarta en pares para no romper la alternancia de
  roles, y el system prompt no se guarda como mensaje: se re-renderiza en cada turno a
  partir de la metadata actual.
- **`project_metadata` separada del historial.** Facts sobre el proyecto en curso
  (`project_name`, `assumed_team_size`, `mentioned_technologies`, `agreed_scope`) que
  viajan en el system prompt y sobreviven a los turnos que la ventana deslizante
  descarta. Se extrae con una segunda llamada al LLM y se combina con el valor anterior:
  los escalares se sobrescriben solo si vienen distintos de `null`, las tecnologías se
  unen sin duplicar.
- **Adjuntos.** PDFs y Word se extraen localmente y se concatenan a la transcripción
  entre vallas explícitas antes de construir el prompt. Dos topes: bytes por archivo y
  caracteres extraídos.
- **Inspección del estado.** `GET /api/v1/sessions/{session_id}` devuelve la metadata y
  el número de turnos retenidos.
- **Cliente Streamlit.** Crea la sesión al cargar la página, acepta varios adjuntos,
  muestra la metadata en el panel lateral y ofrece "Nueva conversación".

No hay cambios en el contrato de `POST /api/v1/estimate`: sigue funcionando como estaba.

## Capabilities

### New Capabilities

- `memoria-conversacional`: ciclo de vida de las sesiones, historial con ventana
  deslizante, `project_metadata` como conocimiento del proyecto separado del historial,
  y su inspección por HTTP.
- `adjuntos`: extracción de texto de PDF y Word, enriquecimiento de la transcripción con
  vallas, topes de tamaño y traducción de fallos a códigos HTTP.

### Modified Capabilities

- `estimacion-transcripcion`: se añade el endpoint multi-turno con `session_id` y
  adjuntos. El endpoint existente no cambia.
- `prompts-versionados`: nueva versión `v3` con el bloque `<project_metadata>` en el
  system prompt, y una familia de plantillas nueva para el extractor de metadata.
- `interfaz-conversacional`: la interfaz pasa a ser basada en sesión, con selector de
  adjuntos y panel de metadata; se relaja el requisito de streaming en la capa de
  interfaz, que el formulario del módulo 04 ya no cumplía.

## Impact

**Código nuevo**

- `app/schemas/session.py`, `app/services/sessions.py`, `app/services/attachments.py`,
  `app/services/metadata.py`
- `app/routers/sessions.py`
- `app/prompts/estimation/v3/`, `app/prompts/metadata_extraction/v1/`

**Código modificado**

- `app/config.py`: `llm_prompt_version` pasa a admitir `v3`; nuevas settings de sesión y
  adjuntos.
- `app/prompts/loader.py`: segunda función de render para el extractor.
- `app/services/llm_service.py`: generar con historial y system promptYa construidos.
- `app/main.py`, `streamlit_app.py`.

**Dependencias nuevas**

- `python-multipart` (FastAPI la necesita para `UploadFile`; hoy solo llega de forma
  transitiva a través de Streamlit y no está declarada)
- `pypdf`, `python-docx`

**Riesgos**

- El estado en memoria se pierde en cada reinicio: con `uvicorn --reload` cualquier
  guardado invalida el `session_id` del cliente. El backend responde `404` y el cliente
  se recupera creando una sesión nueva.
- Los handlers son `def`, así que Starlette los ejecuta en un threadpool: el
  diccionario de sesiones necesita un lock para que un `append` y un recorte no se
  entrelacen.

**Fuera de alcance** (propio del enunciado): caché de respuestas, guardrails de salida,
structlog, resumen acumulativo con anclas, tier dinámico, Actor-Critic-Boss y
persistencia de la memoria.