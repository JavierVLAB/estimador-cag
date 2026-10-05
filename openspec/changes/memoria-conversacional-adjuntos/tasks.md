## 1. Dependencias y configuración

- [ ] 1.1 Declarar `python-multipart` en `pyproject.toml` de forma explícita: FastAPI la necesita para `UploadFile` y hoy solo llega como dependencia transitiva de Streamlit.
- [ ] 1.2 Añadir `pypdf` y `python-docx` a las dependencias.
- [ ] 1.3 Añadir a `Settings` y documentar en `.env.example`: `session_max_turns` (6), `max_attachment_bytes`, `max_attachment_chars` y `max_attachments_per_request`.

## 2. Estado de sesión

- [ ] 2.1 Crear `app/schemas/session.py` con `ProjectMetadata` (campos opcionales, `is_empty()`, `merge_with()` que sobrescribe escalares no nulos y une tecnologías sin duplicar) y los contratos de creación, respuesta de estimación e inspección de sesión.
- [ ] 2.2 Crear `app/services/sessions.py` con `ConversationHistory`: `append()` de pares user/assistant, recorte en pares que ajusta a par si el sobrante es impar, y `to_messages()` que devuelve solo usuario/asistente.
- [ ] 2.3 Añadir `Session` con `session_id` (uuid4), historial, metadata y fecha de creación, con docstring que explique por qué se acepta la volatilidad en esta fase.
- [ ] 2.4 Implementar `SessionStore` con `create()`, `get_or_404()` y `SessionNotFoundError`, protegido por `threading.Lock` porque los handlers corren en el threadpool.
- [ ] 2.5 Tests unitarios: fusión de metadata (escalar corregido, escalar ausente preservado, tecnologías sin duplicar), límite de turnos, recorte que preserva la alternancia de roles y `is_empty()` en el primer turno.

## 3. Adjuntos

- [ ] 3.1 Crear `app/services/attachments.py` con `extract_text()`: despacho por extensión, `pypdf` para PDF y `python-docx` para Word, con imports perezosos dentro de las funciones.
- [ ] 3.2 Rechazar por tamaño **antes** de leer el contenido, y truncar el texto extraído al máximo de caracteres registrando cuánto se descartó.
- [ ] 3.3 Definir `AttachmentExtractionError` y `UnsupportedAttachmentError` con el nombre de archivo, y `enrich_transcript()` con las vallas `--- attachment: <nombre> ---` / `--- end attachment ---`.
- [ ] 3.4 Traducir los fallos a HTTP: `413` por exceso de bytes, `415` por extensión no soportada, `422` por archivo corrupto o por exceso de número de adjuntos, sin filtrar trazas.
- [ ] 3.5 Tests con un PDF y un Word generados en el propio test, más un PDF corrupto, una extensión no soportada y un archivo por encima del tope de bytes.

## 4. Prompts

- [ ] 4.1 Crear `app/prompts/estimation/v3/` con `system.j2` y `user.j2`, incluyendo el bloque `<project_metadata>` delimitado y presente también cuando la metadata esté vacía.
- [ ] 4.2 Crear `app/prompts/metadata_extraction/v1/` con `system.j2` y `user.j2` que indiquen devolver `null` ante la duda, no inventar hechos y normalizar la capitalización de las tecnologías.
- [ ] 4.3 Añadir al cargador la segunda función de render y las variables de contexto necesarias; permitir `v3` en el `Literal` de `llm_prompt_version`.
- [ ] 4.4 Tests de render: bloque de metadata con hechos y con metadata vacía, y que las plantillas del extractor no se confundan con las de estimación.

## 5. Servicio de generación y extracción de metadata

- [ ] 5.1 Añadir a `llm_service` una función que genere a partir de un historial y un system prompt ya construidos, sin que el módulo conozca el modelo de sesiones; reutilizar la normalización de errores y consumo ya existente.
- [ ] 5.2 Crear `app/services/metadata.py` con la llamada al extractor, validación del JSON resultante y fusión mediante `merge_with`.
- [ ] 5.3 Degradación graciosa: si el extractor falla o devuelve algo no interpretable, conservar la metadata anterior y devolver la estimación igualmente, dejando constancia en el log.
- [ ] 5.4 Tests: un turno aporta hechos y actualiza la metadata; un extractor que lanza o devuelve basura no impide la respuesta.

## 6. Router de sesiones

- [ ] 6.1 Crear `app/routers/sessions.py` con `POST /sessions` (`201` + `session_id`), `GET /sessions/{session_id}` y `POST /sessions/{session_id}/estimate` en `multipart/form-data`.
- [ ] 6.2 Encadenar el turno: resolver sesión, enricher transcript, renderizar ambos mensajes, generar, extraer y fusionar metadata, y añadir el turno al historial.
- [ ] 6.3 Traducir `SessionNotFoundError` a `404` con motivo identificable y `LLMServiceError` a `502`, como ya hace el router de estimaciones.
- [ ] 6.4 Montar el router en `app/main.py` con el prefijo `/api/v1`.

## 7. Cliente Streamlit

- [ ] 7.1 Crear la sesión al cargar la página y conservar el `session_id` en `session_state`.
- [ ] 7.2 Enviar la estimación al endpoint de sesión como `multipart/form-data`, incluyendo los adjuntos del selector múltiple.
- [ ] 7.3 Mostrar el `project_metadata` y el número de turnos retenidos en el panel lateral, actualizándolos tras cada turno, y distinguir "todavía vacío" de error.
- [ ] 7.4 Añadir "Nueva conversación": pedir sesión nueva, limpiar resultado y vaciar el panel.
- [ ] 7.5 Recuperarse de una sesión perdida: detectar el `404`, comunicarlo y crear una sesión nueva sin descartar la transcripción ya escrita.
- [ ] 7.6 Tests con `AppTest`: creación de sesión al cargar, envío con adjuntos, refresco del panel y recuperación tras `404`.

## 8. Verificación final

- [ ] 8.1 Test de los tres escenarios del paso 7 del enunciado: metadata actualizada entre dos peticiones, un adjunto que cambia la estimación, y ocho turnos sin superar el límite en el array `messages` realmente enviado.
- [ ] 8.2 Ejecutar `uv run pytest` y registrar el resultado; ningún test debe necesitar API keys ni tráfico real.
- [ ] 8.3 `openspec validate --all` en verde.
- [ ] 8.4 Actualizar el README: el camino de adjuntos elegido y por qué, cómo se extrae la `project_metadata`, el coste de la llamada extra, el comportamiento con `--reload` y el cambio de "servicio sin estado" a "memoria de sesión".
- [ ] 8.5 Corregir en el README y en `CLAUDE.md` cualquier afirmación que quede contradicha por el estado en memoria del proceso.