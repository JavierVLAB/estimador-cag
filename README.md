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
proyecto **no tiene** base de datos, recuperación, almacén vectorial,
persistencia ni caché: es una decisión, no algo pendiente de hacer.

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
| `app/routers/estimations.py` | Endpoint HTTP: validación de entrada y formato de salida |
| `app/services/llm_service.py` | Construcción del prompt y llamada al proveedor LLM |
| `app/context/examples.py` | Las estimaciones de referencia (el contexto CAG) |
| `app/config.py` | Configuración; único punto que lee variables de entorno |

Las dependencias van en una sola dirección: `routers → services → context`. El
servicio no sabe que existe FastAPI, y el contexto es solo datos. Así, el día
que se sustituya el contexto estático por recuperación, solo cambian esas dos
capas.

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
| `POST` | `/api/v1/estimate` | Genera una estimación a partir de una transcripción |
| `GET` | `/docs` | Documentación interactiva (Swagger UI) |

### Ejemplo

```bash
curl -X POST http://localhost:8000/api/v1/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "transcription": "En la reunión con el equipo de marketing, el cliente explicó que necesita una landing page con formulario de contacto, integración con su CRM actual (HubSpot), y una sección de blog con editor WYSIWYG. El plazo ideal sería tenerlo listo en 4 semanas. El diseño ya existe en Figma."
  }'
```

Respuesta:

```json
{
  "estimation": "## Estimación: Landing page con integración HubSpot\n\n### Desglose de tareas\n...",
  "model": "gpt-4o-mini",
  "provider": "openai"
}
```

El campo `estimation` es texto en markdown, tal como lo genera el modelo.

### Errores

| Código | Cuándo |
|---|---|
| `422` | La transcripción falta o está vacía. No se llama al modelo |
| `502` | El proveedor LLM falló (credencial incorrecta, modelo inexistente, caída del servicio) |

### Swagger

Con el servidor arrancado, `http://localhost:8000/docs` permite probar el
endpoint desde el navegador, sin necesidad de `curl`.

---

## Tests

```bash
uv run pytest
```

Los tests sustituyen la llamada al LLM por una respuesta fija: **no hacen
peticiones reales** y no necesitan API keys válidas. Cubren el health check, una
estimación correcta, las entradas inválidas, el fallo del proveedor y que los
ejemplos de contexto acaban realmente dentro del prompt.

---

## Mejorar las estimaciones

La calidad del resultado depende de dos cosas, ambas en el código:

1. **Los ejemplos** de `app/context/examples.py`. Son la referencia de formato y
   de criterio de esfuerzo. Cuanto más se parezcan al tipo de estimaciones que
   quieres obtener, mejor será el resultado.
2. **Las instrucciones** (`INSTRUCCIONES`) de `app/services/llm_service.py`, que
   definen el rol del modelo y las reglas que debe seguir.

Para comprobar cómo queda el prompt sin gastar una llamada:

```bash
uv run python -c "from app.services.llm_service import build_system_prompt; print(build_system_prompt())"
```
