# Estimador CAG

**Versión 1.0**

Servicio web que recibe la transcripción de una reunión con un cliente y devuelve
una estimación de software: desglose de tareas con horas, equipo recomendado,
duración, supuestos y riesgos.

La estimación la genera un modelo de lenguaje (LLM). El servicio no calcula nada
por su cuenta: su trabajo es darle al modelo el contexto adecuado y devolver el
resultado.

---

## Cómo funciona

El sistema usa una arquitectura **CAG** (*Context-Augmented Generation*).

La idea es sencilla: el "conocimiento" del sistema son unas pocas estimaciones
que se entregaron en el pasado, y **viajan enteras dentro del prompt en cada
llamada al modelo**. No hay base de datos, ni buscador, ni índice: el contexto
se envía completo, siempre el mismo.

Es lo contrario de RAG (*Retrieval-Augmented Generation*), donde el sistema
busca en un almacén qué fragmentos son relevantes para cada consulta y solo
envía esos.

**¿Por qué CAG aquí?** Porque los datos de referencia son pequeños y caben de
sobra en la ventana de contexto del modelo. Añadir una base de datos y un
buscador no mejoraría el resultado y sí añadiría piezas que mantener. Por eso el
proyecto **no tiene** base de datos, recuperación ni almacén vectorial.

El servicio mantiene **memoria de sesión**: el historial de cada conversación y
el `project_metadata` que el modelo extrae de ella viven en un diccionario del
proceso. Eso no cambia el CAG: el conocimiento de referencia sigue viajando
completo en el prompt, lo que se conserva entre turnos es la conversación, que es
otra cosa.

Las consecuencias son operativas y conviene tenerlas presentes:

* Al reiniciar el servidor se pierde todo. `uvicorn --reload` recarga en cada
  cambio de archivo, así que **cada guardado en `streamlit_app.py` o en `app/`
  borra las conversaciones abiertas**.
* Con varios workers cada uno tiene su propio diccionario, así que dos peticiones
  que caigan en workers distintos pueden no ver la misma sesión.
* No hay una caché de respuestas. Si el tráfico creciera lo suficiente como para
  que el coste por llamada dejara de ser irrelevante, sería la primera pieza que
  tendría que aparecer.

### Memoria conversacional y adjuntos

El endpoint `POST /api/v1/sessions/{id}/estimate` añade un turno a una
conversación abierta. Cada turno hace cuatro cosas:

1. **Extrae el texto de los adjuntos** en el servidor. El binario no se sube al
   proveedor. La alternativa de subirlo exigiría duplicar el camino para OpenAI y
   Anthropic, cuyo formato de archivo es distinto, y dejaría el texto sin
   normalizar para el futuro módulo de RAG. Se pierde el layout visual.
2. **Renderiza el system prompt** con el `project_metadata` vigente. No se guarda
   en el historial: se vuelve a construir en cada llamada, porque cambia cuando la
   metadata cambia.
3. **Genera la estimación** con el historial de turnos anteriores, en una ventana
   deslizante de `SESSION_MAX_TURNS` pares.
4. **Extrae el `project_metadata`** con una segunda llamada al LLM y lo fusiona
   con el anterior.

Sobre el paso 4, la decisión tiene un precio: **duplica la latencia de cada turno**
y añade una segunda factura de entrada por turno. La alternativa
barata, un `regex` sobre la respuesta, obligaría a intercalar un bloque de campos
dentro de la estimación que la persona usuaria lee, y esa estimación es
justamente lo que el servicio tiene que entregar limpio. Aquí el bloque de datos
viaja aparte.

Si el extractor falla o devuelve algo que no es JSON interpretable, la
**estimación se entrega igual** con la metadata anterior. Perder un dato de
contexto no justifica perder la respuesta que se pidió.

Los adjuntos tienen dos topes, porque atacan riesgos distintos: `MAX_ATTACHMENT_BYTES`
se comprueba antes de procesar el archivo y protege el proceso;
`MAX_ATTACHMENT_CHARS` acota lo que llega al contexto. `MAX_ATTACHMENTS_PER_REQUEST`
acota el caso de muchos documentos pequeños que en conjunto desbordan. El texto de
cada adjunto viaja en el prompt entre vallas que llevan su nombre, para que el
modelo distinga la documentación de lo que se dijo en la reunión.

### El flujo, paso a paso

```
   Cliente HTTP
        │  POST /api/v1/estimate  { "transcription": "..." }
        ▼
   ┌─────────────────────────────────────────┐
   │ app/routers/estimations.py              │  1. Valida la entrada
   │                                         │     (rechaza texto vacío)
   └───────────────────┬─────────────────────┘
                       ▼
   ┌─────────────────────────────────────────┐
   │ app/services/llm_service.py             │  2. Construye el prompt:
   │                                         │     instrucciones + ejemplos
   │   build_system_prompt()  ◄──────────────┼──  app/context/examples.py
   │                                         │     (las estimaciones previas)
   │   generate_estimation()                 │  3. Llama al proveedor LLM
   └───────────────────┬─────────────────────┘     (OpenAI o Anthropic)
                       ▼
   ┌─────────────────────────────────────────┐
   │ app/routers/estimations.py              │  4. Devuelve el JSON
   └───────────────────┬─────────────────────┘
                       ▼
   { "estimation": "## Estimación...", "model": "...", "provider": "..." }
```

Los mensajes que recibe el modelo siguen este patrón:

| Mensaje | Contenido |
|---|---|
| `system` | Instrucciones del rol + las estimaciones de referencia completas |
| `user` | La transcripción que hay que estimar |
| `assistant` | La estimación generada (la respuesta del modelo) |

### Qué hace cada archivo

| Archivo | Responsabilidad |
|---|---|
| `app/main.py` | Aplicación FastAPI, health check y montaje del router |
| `app/routers/estimations.py` | Endpoint HTTP sin sesión: validación de entrada y formato de salida |
| `app/routers/sessions.py` | Endpoints de sesión y encadenado del turno |
| `app/services/llm_service.py` | Construcción del prompt y llamada al proveedor LLM |
| `app/services/sessions.py` | Historial con ventana deslizante y diccionario de sesiones |
| `app/services/attachments.py` | Extracción de texto de PDF y Word, y su fusión con la transcripción |
| `app/services/metadata.py` | Extracción y fusión del `project_metadata` |
| `app/prompts/loader.py` | Render de las plantillas versionadas |
| `app/context/examples.py` | Las estimaciones de referencia (el contexto CAG) |
| `app/config.py` | Configuración; único punto que lee variables de entorno |

Las dependencias van en una sola dirección: `routers → services → context`. El
servicio no sabe que existe FastAPI, y el contexto es solo datos. Así, el día
que se sustituya el contexto estático por recuperación, solo cambian esas dos
capas.

Dos detalles de esa frontera que conviene no perder: `llm_service` no sabe nada
de sesiones, por eso recibe el system prompt ya construido en lugar de
renderizarlo; y el `SessionStore` vive en el router porque es estado del proceso
que pertenece a la capa HTTP, no al servicio que define la forma de `Session`.

---

## Puesta en marcha

Requisitos: **Python 3.11+** y [`uv`](https://docs.astral.sh/uv/) como gestor de
paquetes.

```bash
# 1. Instalar dependencias
uv sync

# 2. Crear tu archivo de configuración a partir de la plantilla
cp .env.example .env
#    Edita .env y pon tu API key

# 3. Arrancar el servidor
uv run uvicorn app.main:app --reload
```

El servicio queda disponible en `http://localhost:8000`.

### Variables de entorno

Se definen en `.env` (que nunca se sube al repositorio). La plantilla está en
`.env.example`.

| Variable | Descripción | Por defecto |
|---|---|---|
| `OPENAI_API_KEY` | API key de OpenAI | — (necesaria si usas OpenAI) |
| `ANTHROPIC_API_KEY` | API key de Anthropic | — (necesaria si usas Anthropic) |
| `LLM_PROVIDER` | Proveedor: `openai` o `anthropic` | `openai` |
| `LLM_MODEL` | Modelo a utilizar | `gpt-4o-mini` |
| `LLM_PROMPT_VERSION` | Versión de instrucciones del endpoint sin estado: `v1`, `v2` o `v3` | `v1` |
| `SESSION_MAX_TURNS` | Pares usuario/asistente que retiene cada sesión | `6` |
| `MAX_ATTACHMENT_BYTES` | Tope por archivo, comprobado antes de procesarlo | `10000000` |
| `MAX_ATTACHMENT_CHARS` | Tope del texto extraído de un adjunto que llega al prompt | `20000` |
| `MAX_ATTACHMENTS_PER_REQUEST` | Número máximo de adjuntos por turno | `5` |
| `LLM_TIMEOUT_SECONDS` | Timeout de cada llamada al LLM (el SDK usa 600 s si no se fija) | `30.0` |
| `LLM_MAX_RETRIES` | Reintentos ante errores transitorios del proveedor | `2` |
| `LLM_MAX_OUTPUT_TOKENS` | Techo de tokens de salida; si se alcanza, la respuesta se trata como error | `2000` |
| `APP_ENV` | Entorno de ejecución | `development` |
| `LOG_LEVEL` | Nivel de logging | `DEBUG` |

**Elegir proveedor y modelo.** `LLM_PROVIDER` y `LLM_MODEL` son variables
independientes, así que hay que cambiar las dos a la vez:

```bash
# OpenAI
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini

# Anthropic
LLM_PROVIDER=anthropic
LLM_MODEL=claude-haiku-4-5
```

Si dejas `LLM_PROVIDER=anthropic` con un modelo de OpenAI (o al revés), la
llamada fallará y el servicio responderá `502`.

---

## Uso

### Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/health` | Comprueba que el servicio responde |
| `POST` | `/api/v1/estimate` | Genera una estimación a partir de un formulario guiado |
| `POST` | `/api/v1/sessions` | Abre una conversación y devuelve su identificador |
| `GET` | `/api/v1/sessions/{id}` | Consulta el `project_metadata` y los turnos retenidos |
| `POST` | `/api/v1/sessions/{id}/estimate` | Añade un turno a la conversación, con adjuntos opcionales |
| `GET` | `/docs` | Documentación interactiva (Swagger UI) |

Los tres endpoints de sesión no llaman a base de datos: el estado vive en un
diccionario del proceso y se pierde al reiniciar el servidor.

### Ejemplo

```bash
curl -X POST http://localhost:8000/api/v1/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Aplicación web para gestionar las reservas de un centro deportivo, con pagos, calendario para clientes y un área interna para el personal.",
    "project_type": "web_saas",
    "detail_level": "medium",
    "output_format": "phases_table"
  }'
```

Respuesta:

```json
{
  "text": "## Estimación\n\n| Fase | Horas | ...",
  "prompt_version": "v1",
  "model": "gpt-4o-mini",
  "provider": "openai",
  "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
}
```

El campo `text` es texto en Markdown, tal como lo genera el modelo. La versión
`v1` identifica las plantillas que construyeron las instrucciones de esa llamada.

### Errores

| Código | Cuándo |
|---|---|
| `422` | Falta un campo del formulario, una opción no es válida o la descripción tiene menos de 20 o más de 2.000 caracteres. No se llama al modelo |
| `502` | El proveedor LLM falló o devolvió una respuesta truncada/vacía (credencial incorrecta, modelo inexistente, caída del servicio) |
| `500` | Un error propio del código (no del proveedor) |

Los errores del proveedor se distinguen de los bugs del servicio: solo los
primeros responden `502`. Un error interno se reporta como `500`.

### Swagger

Con el servidor arrancado, `http://localhost:8000/docs` permite probar el
endpoint desde el navegador, sin necesidad de `curl`.

---

## Formulario de estimación (Streamlit)

Además del API HTTP, el proyecto incluye una interfaz (`streamlit_app.py`) para
describir un proyecto, seleccionar su tipo, el nivel de detalle y el formato de
la estimación, y adjuntar documentación. Cada envío es **un turno más de la misma
conversación**: la interfaz abre una sesión al cargar y envía a
`POST /api/v1/sessions/{id}/estimate`.

El panel lateral muestra el `project_metadata` que el modelo ha ido extrayendo y
cuántos turnos se conservan. Cuando todavía no hay datos se dice explícitamente,
porque es un estado normal del primer turno y no un fallo.

Si el backend responde `404` porque la sesión ya no existe (habría que reiniciar
el servidor), la interfaz abre una sesión nueva y reintenta el turno una vez: la
transcripción que la persona había escrito no se pierde por un reinicio.

Primero arranca el backend:

```bash
uv run uvicorn app.main:app --reload
```

En otra terminal, arranca la interfaz:

```bash
uv run streamlit run streamlit_app.py
```

La interfaz abre en el navegador (por defecto en `http://localhost:8501`) y se
conecta por defecto a `http://localhost:8000`. Si el backend está en otra
dirección, define `ESTIMATOR_API_BASE_URL` antes de arrancar Streamlit.

Las instrucciones están en `app/prompts/`, separadas por versiones. El endpoint
sin estado selecciona su versión con `LLM_PROMPT_VERSION`; los turnos de sesión
usan siempre `v3`, que es la única que recibe el `project_metadata` y las reglas
de continuidad. No es configurable a propósito: sin ese bloque, un turno sería una
estimación aislada sin el contexto que el enunciado pide. Las instrucciones del
extractor de metadata están en `app/prompts/metadata_extraction/`.

El formulario no elige versión de prompt ni llama directamente a OpenAI o
Anthropic. En el panel lateral se muestran, en solo lectura, el prompt que se
envía y las métricas de la última llamada.

Cada estimación deja un registro seguro con la versión, proveedor, modelo,
huella SHA-256 y tamaños de los mensajes. El registro no incluye la descripción
de la persona usuaria ni el contenido de las instrucciones.

---

## Tests

```bash
uv run pytest
```

Los tests sustituyen la llamada al LLM por una respuesta fija: **no hacen
peticiones reales** y no necesitan API keys válidas. Cubren el formulario HTTP,
las opciones inválidas, el fallo del proveedor, el streaming y el render de las
plantillas según el formato y nivel de detalle elegidos.

---

## Mejorar las estimaciones

La calidad del resultado depende de dos cosas, ambas versionadas como plantillas:

1. **Los ejemplos** de `app/prompts/estimation/<versión>/examples.j2`. Son la referencia de formato y
   de criterio de esfuerzo. Cuanto más se parezcan al tipo de estimaciones que
   quieres obtener, mejor será el resultado.
2. **Las instrucciones** (`system.j2`) de `app/prompts/estimation/<versión>/`, que
   definen el rol del modelo y las reglas que debe seguir.

Para comprobar cómo queda el prompt sin gastar una llamada:

```bash
uv run python -c "from app.prompts.loader import render_estimation_prompt; from app.schemas.estimation import EstimationRequest, ProjectType, DetailLevel, OutputFormat; r = EstimationRequest(description='Aplicación web para organizar reservas y pagos de un centro deportivo.', project_type=ProjectType.WEB_SAAS, detail_level=DetailLevel.MEDIUM, output_format=OutputFormat.PHASES_TABLE); print(render_estimation_prompt(r)[0])"
```
