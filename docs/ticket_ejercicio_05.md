# Ticket — Memoria conversacional y adjuntos (ejercicio 05)

**Fecha:** 2026-10-05
**Fuente:** `docs/ejercicio_05.md`
**Prioridad:** Alta (plazo: hoy, lunes 5 de octubre, fin del día)
**Estado:** Abierto
**Depende de:** `modulo-04-formulario-prompts` (pendiente de cerrar, ver §7)

---

## Resumen

El estimador es hoy un sistema transaccional: entra una transcripción, sale una
estimación, y no queda nada. El enunciado del 05 le añade dos piezas:

1. **Memoria conversacional en memoria del proceso**, identificada por un
   `session_id`: historial con ventana deslizante y `project_metadata` separado.
2. **Adjuntos** en `multipart/form-data`: PDFs y Word que enriquecen la
   transcripción.

Lo que **no** entra (del propio enunciado): resumen acumulativo con anclas, tier
dinámico en runtime, persistencia entre reinicios, búsqueda web, function
calling, y el patrón Actor-Critic-Boss. Todo eso es contenido del directo.

---

## 1. Punto de partida verificado

Rama `pre-session-04`, 42 tests en verde. El enunciado da por hecho un punto de
partida que en este repo es solo parcialmente cierto:

| El enunciado da por hecho | Realidad en `pre-session-04` |
|---|---|
| Wrapper de proveedores OpenAI/Anthropic | ✅ `app/services/llm_service.py` |
| Templates Jinja2 versionados | ✅ `estimation/v1` y `estimation/v2` |
| Cliente con formulario tipado | ✅ `streamlit_app.py` (conecta y pinta la respuesta) |
| Salida validada por schema Pydantic | ⚠️ El schema valida la *envoltura* HTTP; la estimación en sí es Markdown libre, no un modelo estructurado |
| Cacheo de respuestas | ❌ No existe |
| Guardrails sobre la salida | ❌ No existen |
| Observabilidad con structlog | ❌ `logging` estándar + huella sha256 del prompt |

**Conclusión:** caché, guardrails y structlog son residuos del guion de la sesión 04,
no requisitos del 05. No se implementan. No se elimina el trabajo ya hecho.

Detalles que sí condicionan el diseño:

- `app/config.py` declara `llm_prompt_version: Literal["v1", "v2"]`. Añadir el
  bloque `<project_metadata>` obliga a crear `v3` y a tocar ese `Literal`.
- `llm_service.generate_estimation_stream` existe y tiene tests, pero **ningún
  endpoint lo usa**. El cliente Streamlit hace POST normal. No es una regresión
  del 05; se deja como está.
- `python-multipart` está instalada pero como dependencia transitiva de
  Streamlit. FastAPI la necesita para `UploadFile` y no está declarada en
  `pyproject.toml`.
- Los tests usan `TestClient` síncrono con el servicio sustituido por un doble
  (`tests/conftest.py`). No hay `pytest-asyncio`.

---

## 2. Decisiones

### D1. Adjuntos: Camino B (extracción local)

`pypdf` para PDF y `python-docx` para Word. El texto extraído se concatena a la
transcripción entre vallas explícitas antes de construir el prompt.

**Por qué.** Desacopla del proveedor (el mismo camino sirve para OpenAI y
Anthropic sin tocar código), permite probar la extracción sin llamadas reales al
LLM, y deja el texto ya normalizado para el chunking de RAG del módulo 3. El
Camino A ata la implementación a la Files API de un proveedor concreto y no es
testeable sin red.

### D2. `project_metadata`: extractor LLM (segunda llamada)

Tras cada respuesta se hace una llamada adicional a un prompt propio
(`metadata_extraction/v1`) que devuelve el `ProjectMetadata` en JSON. Se
combina con el valor anterior mediante `merge_with`: los escalares se
sobrescriben solo si vienen distintos de `null`, y las tecnologías se unen sin
duplicar (case-insensitive).

**Por qué.** La alternativa —heurística con regex sobre el Markdown— obliga a
que la estimación que ve la persona usuaria contenga un bloque de metadatos que
hay que recortar después, y atarte a un formato de prosa que el modelo puede no
respetar. El extractor deja la estimación limpia y hace el trabajo semántico de
verdad ("¿de qué proyecto hablamos?" no es una cuenta de palabras).

**Coste asumido.** Una llamada extra por turno. Se mitiga con degradación
elegante: si la extracción falla, la estimación ya se ha generado y se devuelve
igual, conservando la metadata anterior. **Si falla el extractor no se pierde la
estimación.**

**Alternativa si Javi prefiere cheaper:** heurística con contrato de formato.
Afecta a un solo módulo (`app/services/metadata.py`), el resto no cambia.

### D3. Los cuatro parámetros tipados se conservan

`POST /sessions/{id}/estimate` acepta `multipart/form-data` con `transcript` y
`attachments`, **más** `project_type`, `detail_level` y `output_format` como
campos `Form(...)`.

**Por qué.** El enunciado no dice qué pasa con ellos y el formulario del
módulo 04 los produce. Descartarlos rompería el cliente sin ganancia. Fijarlos al
crear la sesión cuesta de explicar (el formato de salida es por turno) y
exigiría rehacer el formulario.

### D4. El system prompt no es un mensaje del historial

`ConversationHistory` guarda solo pares `user`/`assistant`. El system prompt se
re-renderiza en cada turno desde el `project_metadata` actual y lo antepone el
servicio.

**Por qué.** El enunciado (paso 5) pide "el system prompt regenerado a partir
del `project_metadata` actual". Guardarlo como mensaje fijo obligaría a
reescribirlo en cada turno, y la "invariante" se vuelve una mentira en cuanto la
metadata cambia.

### D5. Concurrencia: el store lleva un lock

Los handlers actuales son `def`, así que Starlette los ejecuta en un threadpool.
El diccionario de sesiones se protege con `threading.Lock`. Sin esto, dos
peticiones simultáneas sobre la misma sesión pueden entrelazar el `append` y el
recorte de la ventana.

### D6. Sesión desconocida → `404`, y el cliente se recupera

Con `uvicorn --reload` (el comando que documenta el proyecto) cualquier guardado
reinicia el proceso y el `session_id` del cliente queda huérfano. Decisión: el
backend responde `404` con un motivo explícito —es la semántica correcta— y el
cliente Streamlit detecta ese `404`, avisa y crea sesión nueva en lugar de
fallar. Evita el "sesión perdida" en mitad de una demo.

### D7. Topes de adjuntos (dos, no uno)

- `max_attachment_bytes`: si el archivo lo supera, se rechaza antes de leerlo.
  Sin este tope, un PDF de 200 MB se lee entero en RAM aunque el texto extraído
  se recorte después.
- `max_attachment_chars`: el texto extraído se trunca y se registra cuánto se
  descartó.

Añadir solo el segundo es insuficiente: protege el prompt, no el proceso.

### D8. New settings

`session_max_turns` (6), `max_attachment_bytes`, `max_attachment_chars`,
`max_attachments_per_request`. Todas van en `app/config.py` y `.env.example`.

---

## 3. Alcance

**Dentro.**

- `app/schemas/session.py`: `ProjectMetadata`, contrato de creación de sesión,
  contrato de respuesta de sesión.
- `app/services/sessions.py`: `ConversationHistory`, `Session`, `SessionStore`.
- `app/services/attachments.py`: extracción y enriquecimiento de la transcripción.
- `app/services/metadata.py`: llamada al extractor y `merge_with`.
- `app/prompts/estimation/v3/` y `app/prompts/metadata_extraction/v1/`.
- `app/routers/sessions.py`: los tres endpoints.
- `app/prompts/loader.py`: segunda función de render.
- `app/main.py`: montaje del router.
- `streamlit_app.py`: sesión, adjuntos, panel de metadata, nueva conversación.
- `tests/`: los tres escenarios del paso 7.
- `pyproject.toml`: `python-multipart` explícita, `pypdf`, `python-docx`.
- `.env.example`, `README.md`.

**Fuera.**

- Caché de respuestas, guardrails de salida, structlog (ver §1).
- Resumen acumulativo, anclas, tier dinámico, Actor-Critic-Boss.
- Persistencia: el store es un diccionario en memoria del proceso.
- Streaming en el endpoint nuevo (no lo pide el enunciado).
- Cambiar el contrato de `POST /api/v1/estimate`. Sigue funcionando como estaba.

---

## 4. Plan de trabajo

Cada paso deja el repo verde (`uv run pytest`).

1. **Cerrar la sesión 04** (§7) para partir de una base limpia.
2. **Store y contratos.** `ProjectMetadata` + `merge_with`, `ConversationHistory`
   con `_trim()` en pares, `Session`, `SessionStore` con lock. Tests unitarios.
3. **Adjuntos.** `extract_text()` con topes, `enrich_transcript()` con las
   vallas `--- attachment: <nombre> ---` / `--- end attachment ---`. Excepciones
   de dominio y su mapeo a `415` / `413` / `422`.
4. **Prompts.** `estimation/v3` con el bloque `<project_metadata>`;
   `metadata_extraction/v1`. Segunda función de render en el loader.
5. **Router.** `POST /sessions` (201), `GET /sessions/{id}`,
   `POST /sessions/{id}/estimate`. Degradación elegante del extractor.
6. **Cliente.** `session_id` en `session_state` creado al cargar la página,
   `st.file_uploader` múltiple, panel lateral con la metadata, botón de nueva
   conversación, recuperación ante `404`.
7. **Tests del paso 7.** Los tres escenarios.
8. **README y rama** `pre-session-05`.

---

## 5. Criterios de aceptación

Taken de "Criterios de hecho" del enunciado, más lo que este ticket añade:

- [ ] `POST /api/v1/sessions` crea una sesión y devuelve `session_id` (UUID v4).
- [ ] `POST /api/v1/sessions/{session_id}/estimate` acepta `multipart/form-data`
      con `transcript`, los tres campos tipados y `attachments` opcionales, y
      devuelve una estimación con el schema existente.
- [ ] Tras varios turnos, la respuesta mantiene coherencia con el proyecto en
      curso: el nombre del proyecto no se olvida entre turnos.
- [ ] `project_metadata` se actualiza de forma visible entre turnos y se expone en
      `GET /sessions/{session_id}`.
- [ ] El historial enviado al LLM nunca supera `session_max_turns` pares.
- [ ] Un PDF adjunto cambia el resultado de la estimación.
- [ ] Un adjunto con extensión no soportada devuelve `415`; uno corrupto, `422`;
      uno por encima del tope de bytes, `413`.
- [ ] Un fallo del extractor de metadata **no** hace fallar la estimación.
- [ ] `README.md` dice qué camino de adjuntos se eligió, con qué criterio, y cómo
      se extrae la `project_metadata`.
- [ ] `uv run pytest` pasa sin API keys ni tráfico real.
- [ ] `.env.example` documenta las variables nuevas, sin valores reales.

---

## 6. Riesgos

| Riesgo | Mitigación |
|---|---|
| Plazo el mismo día | Plan ordenado por pasos verdes; cliente y README son los últimos |
| No se puede arrancar el servidor (regla del proyecto) | Todo se verifica con `TestClient` y dobles; la comprobación manual queda para Javi |
| Coste por turno ×2 con el extractor | Degradación elegente + `llm_max_output_tokens` acotado en el extractor |
| `--reload` tumba las sesiones | D6: el cliente se recupera |
| Acoplar el estado de sesión al diseño CAG "sin estado" | La memoria es de sesión; el conocimiento de referencia sigue viajando completo en el prompt. Se documenta en `CLAUDE.md` |

---

## 7. Cierre pendiente de la sesión 04

Tres changes de OpenSpec siguen abiertos:

| Change | Tasks | Acción |
|---|---|---|
| `robustez-llm-entrada` | 18/18 | Archivar |
| `rediseno-ui-streamlit` | 16/16 | Archivar |
| `modulo-04-formulario-prompts` | 11/14 | 4.2 ya está implementado en `streamlit_app.py` (verificado por lectura y por los tests del cliente). 4.3 y 5.3 son comprobaciones manuales de interfaz: requieren arrancar la app, que no hace el agente. |

Además, `openspec/specs/estimacion-transcripcion` fija `prompt_version = "v1"`,
pero `v2` ya existe y es configurable. Al archivar hay que decidir si la spec
sube a "la versión configurada" o se deja el `v1` literal.

---

## 8. Referencia del curso (revisada 2026-10-05)

El enunciado apunta a `solutions/session-05` y a `tree/session_5`. **Ninguna de
las dos existe** en `LIDR-academy/ai-engineering`. No hay tags. Las ramas son
`main`, `session_2`, `session_2_live` y `agents_event`.

`main` sí contiene la implementación final del curso completo (sesiones 2→11+,
con langgraph, alembic, redis, pgvector, presidio). Confirmó dos decisiones de
este ticket: **Camino B** para adjuntos, y los cuatro parámetros tipados como
`Form(...)` junto a `transcript` y `attachments`. Se usa como referencia de
contrato, **no** como plantilla: copiarla arrastraría el tier resolver, las
anclas, el resumen y el patrón ACB, que son contenido del directo.