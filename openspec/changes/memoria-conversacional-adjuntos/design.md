# Diseño — memoria conversacional y adjuntos

## Contexto

El servicio tiene tres piezas que no encajan todavía: un schema de petición que exige
cuatro campos, un `llm_service` que genera desde un único `(system, user)` y un cliente
Streamlit que es un formulario. El ejercicio mete una sesión entre medias sin tocar el
contrato público de `POST /api/v1/estimate`.

Restricciones que condicionan el diseño:

- La estructura de `app/` la fija el enunciado y no se amplía sin criterio.
- Sin base de datos. El store es un diccionario en memoria del proceso.
- Los handlers actuales son `def`: corren en el threadpool de Starlette.
- Los tests sustituyen el servicio por un doble; nada llama al LLM.

## Decisiones

### D1. Adjuntos por extracción local, no por Files API

El enunciado ofrece dos caminos. Se elige extraer el texto en el proceso con `pypdf` y
`python-docx`.

El camino A (subir el binario al proveedor) ata la implementación a la Files API de un
proveedor concreto, no es ejercitable sin red y no deja el texto normalizado para el
módulo de RAG. El camino B produce el mismo prompt para OpenAI y para Anthropic, se
puede testear con un PDF generado en el test, y adelanta el chunking.

Coste que se asume: se pierde el layout visual y los diagramas. Aceptable, porque la
estimación se apoya en el texto.

### D2. La metadata se extrae con una segunda llamada al LLM

Dos opciones del enunciado: heurística sobre la respuesta, o extractor.

La heurística obliga a que la estimación que ve la persona usuaria lleve dentro un
bloque de campos que después hay que recortar, y ata el sistema a un formato de prosa
que el modelo puede no respetar. El extractor deja la estimación limpia y hace el
trabajo semántico: distinguir "el tamaño del equipo es 4" de un número suelto que
aparezca por ahí es una decisión de lectura, no de regex.

Una llamada extra por turno es un coste real y por eso el extractor:

- va con `llm_max_output_tokens` acotado, porque su respuesta son unos pocos campos;
- falla de forma graciosa. Si el extractor lanza o devuelve JSON inválido, la
  estimación ya generada se devuelve igualmente y la metadata anterior se conserva.

El riesgo residual es la latencia, que se dobla. Se asume y se deja anotado en el
README, porque es justo el punto que se debate en el directo.

### D3. `merge_with`: sobrescribir escalares, unir listas

El extractor devuelve solo lo que ve en el turno. Si el turno no menciona el tamaño del
equipo, devolver `null` debe preservar el valor anterior; si lo menciona y es
distinto, debe corregirlo.

- `project_name`, `assumed_team_size`, `agreed_scope`: gana el valor nuevo si no es
  `None`.
- `mentioned_technologies`: unión sin duplicar, comparando en minúsculas para que
  `Postgres` y `postgres` no se acumulen.

Todo `Optional`, con `is_empty()` para que el primer turno sin metadata sea un estado
legítimo y no un error.

### D4. El system prompt no es un mensaje del historial

El paso 5 del enunciado pide regenerarlo desde la metadata actual. Guardarlo como
mensaje fijo obligaría a reescribirlo en cada turno, y la "invariante" sería mentira en
cuanto la metadata cambiara.

`ConversationHistory` guarda solo pares user/assistant y expone `to_messages()`. El
servicio antepone el system prompt recién renderizado. Coste: cada turno vuelve a pagar
los tokens del system prompt, que es el precio de tener la metadata al día.

### D5. Recorte en pares

Al superar `max_turns` se descartan los pares más antiguos. Si el número de mensajes a
borrar es impar se ajusta a par, porque un historial que empieza por `assistant` rompe
la alternancia que asumen los proveedores.

`append()` no recorta por sí mismo: el recorte es un método aparte. Así hay un único
sitio donde se decide qué se olvida, que es exactamente donde después encajarán el
resumen y las anclas del directo.

### D6. Dos topes en los adjuntos

- `max_attachment_bytes`: se comprueba el tamaño **antes** de leer el archivo. Un único
  tope de caracteres extraídos protege el prompt pero no el proceso: un PDF de 200 MB
  se lee entero en memoria aunque luego se trunque el texto.
- `max_attachment_chars`: el texto extraído se trunca y se registra cuánto se descartó,
  para que el recorte sea visible en los logs en lugar de silencioso.

Con ambos, el peor caso está acotado por el archivo más grande que se acepta, y el
prompt queda acotado por la suma de los topes de caracteres.

### D7. Sesión desconocida: 404 y recuperación en el cliente

Con `uvicorn --reload`, cualquier guardado reinicia el proceso y el `session_id` del
cliente queda huérfano. Un `404` es la semántica correcta para el backend; lo que no
debe pasar es que la interfaz se quede muerta. El cliente detecta ese `404`, lo dice y
crea una sesión nueva.

La alternativa —recrear la sesión en silencio si no existe— dejaría al cliente
conversando con un historial que el backend nunca vio, que es peor.

### D8. Lock en el store

Los handlers son síncronos, así que dos peticiones simultáneas sobre la misma sesión
pueden intercalar un `append` y un recorte. `threading.Lock` en el store; es la pieza
más barata de la lista y evita un fallo intermitente difícil de reproducir.

### D9. Los tres campos tipados se conservan

El enunciado define el endpoint nuevo como `multipart` con `transcript` y `attachments`,
pero no dice qué ocurre con los tres campos que produce el formulario del módulo 04.
Se conservan como `Form(...)`: descartarlos rompería el cliente sin ganancia, y fijarlos
al crear la sesión obligaría a rehacer el formulario y a justificar por qué el formato
de salida sería constante cuando hoy es por turno.

## Estructura

```text
app/
├── schemas/
│   └── session.py          ProjectMetadata, contratos de sesión
├── services/
│   ├── sessions.py         ConversationHistory, Session, SessionStore
│   ├── attachments.py      extracción + enriquecimiento de la transcripción
│   └── metadata.py         llamada al extractor y merge
├── routers/
│   └── sessions.py         POST /sessions, POST /sessions/{id}/estimate, GET /sessions/{id}
└── prompts/
    ├── estimation/v3/      system + user con <project_metadata>
    └── metadata_extraction/v1/
```

`llm_service` gana una función que recibe el historial y el system prompt ya
construidos. La que atiende `POST /api/v1/estimate` se queda como está: no hay por qué
acoplar el endpoint antiguo al modelo de sesiones.

## Flujo de un turno

```text
POST /sessions/{id}/estimate (multipart)
        │
        ├─ store.get_or_404(id)
        ├─ por cada adjunto: tamaño → extract_text → truncar
        ├─ enrich_transcript(transcript, adjuntos)
        ├─ render estimation/v3 con la metadata actual  ── system prompt
        ├─ render estimation/v3 con la transcripción     ── user
        ├─ llm_service.generate(..., history.to_messages())
        ├─ metadata.extract(...) → merge_with(anterior)   ← falla ≠ rompe
        ├─ history.append(user, assistant)
        └─ respuesta: estimación + usage + metadata
```

## Riesgos y cómo se cubren

| Riesgo | Cobertura |
|---|---|
| Doble latencia por el extractor | Degradación graciosa; se documenta el coste en el README |
| Adjuntos que revientan el prompt | Dos topes, uno antes de leer y otro después de extraer |
| Historial corrupto por concurrencia | Lock en el store |
| Sesión perdida con `--reload` | `404` + recuperación del cliente |
| El extractor devuelve JSON inválido | `ValidationError` se captura y se conserva la metadata anterior |
| El estado en memoria contradice el diseño CAG | La memoria es de sesión; el conocimiento de referencia sigue viajando completo en el prompt. Se documenta en `CLAUDE.md` |

## Verificación

Nada llama al LLM. Los doubles capturan el array `messages` final, así que el test de
los ocho turnos comprueba la ventana deslizante sobre lo que se habría enviado de
verdad, no sobre un campo informativo.

- `project_metadata`updated entre turnos.
- Un adjunto cambia el prompt (y con él la estimación).
- Ocho turnos: el array `messages` enviado nunca supera `session_max_turns` pares más el
  system prompt.
- Un PDF corrupto → `422`. Extensión no soportada → `415`. Excede el tope de bytes → `413`.
- Un extractor que falla → la estimación se devuelve igual.