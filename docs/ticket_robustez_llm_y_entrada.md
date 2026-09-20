# Ticket — Robustez de la llamada al LLM y de la entrada

**Fecha:** 2026-09-20
**Fuente:** `docs/revision_ejercicio_02.md`
**Prioridad:** Alta
**Estado:** Abierto

---

## Resumen

La revisión del proyecto frente a `revision_ejercicio_02.md` encontró que el
servicio tiene **seis** de los fallos descritos en la revisión. Ninguno impide
que el camino feliz funcione: todos son fallos de frontera, coste o diagnóstico.
Este ticket los corrige.

Los puntos de la revisión que **no** aplican a este proyecto (verificado) son:

- **Punto 5** — `/health` no desaparece sin API key: las claves son opcionales
  en `config.py` y `/health` no depende del LLM.
- **Punto 7** — No hay `[build-system]` ni carpeta `src/`: `pyproject.toml` es
  de aplicación, no de librería.
- **Punto 10** — No hay middleware CORS.
- **Punto 13a** — El handler es `def` (threadpool), no `async`.
- **Punto 13b** — No existe campo de coste.

---

## Problemas a corregir

### P1. Sin timeout ni reintentos explícitos en los clientes LLM

**Qué.** `app/services/llm_service.py` construye los clientes así:

```python
client = OpenAI(api_key=settings.openai_api_key)
client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
```

El SDK usa de fábrica **600 segundos** con **2 reintentos**: una petición
colgada retiene un worker hasta media hora.

**Arreglo.** Pasar `timeout` y `max_retries` explícitos al construir los
clientes, configurables desde `Settings`:

- New setting `llm_timeout_seconds: float = 30.0`
- New setting `llm_max_retries: int = 2`

### P2. La transcripción no tiene techo de tamaño

**Qué.** `app/routers/estimations.py` valida solo el mínimo:

```python
transcription: str = Field(min_length=1, ...)
```

Cinco megas de texto revientan la ventana de contexto o llega la factura.

**Arreglo.** Añadir `max_length`:

```python
transcription: str = Field(..., min_length=1, max_length=50_000, ...)
```

Pydantic rechaza con `422` en el borde, sin gastar tokens.

### P3. No se acota la salida ni se detecta el truncamiento

**Qué.** En OpenAI no se fija `max_tokens` y en ningún proveedor se lee
`finish_reason` / `stop_reason`. Si la respuesta llega cortada, se devuelve
media estimación con un `200 OK` que miente.

**Arreglo.**

- New setting `llm_max_output_tokens: int = 2000` (se pasa a `max_tokens` en
  OpenAI y a `max_tokens` en Anthropic).
- En `services/llm_service.py`, comprobar `finish_reason == "length"` (OpenAI)
  y `stop_reason == "max_tokens"` (Anthropic); lanzar `LLMServiceError` si la
  respuesta se truncó o si viene vacía.

### P4. `except Exception` maquilla bugs propios como fallo del proveedor

**Qué.** `app/routers/estimations.py` captura `Exception`:

```python
except Exception:
    logger.exception(...)
    raise HTTPException(502, ...)
```

Un `TypeError` o `KeyError` propio aparece como «error del proveedor» ante el
cliente y en los dashboards.

**Arreglo.** El servicio lanza una excepción de dominio `LLMServiceError` para
los fallos del proveedor (envolviendo los errores del SDK) y el router captura
solo esa clase. Los bugs propios vuelven a salir como `500` (FastAPI).

### P8. La transcripción entra al prompt sin frontera

**Qué.** `app/services/llm_service.py` mete la transcripción cruda en el
mensaje `user`:

```python
{"role": "user", "content": transcription},
```

Sin delimitadores, las instrucciones que pudiera contener la transcripción
comptien con las reglas del sistema.

**Arreglo.** Envolver la transcripción en un delimitador impredecible por
petición y decírselo al modelo en el system prompt:

```text
<datos-{marca}>\n{transcription}\n</datos-{marca}>
```

Con `marca = secrets.token_hex(8)`. El atacante no puede cerrar una etiqueta
cuyo nombre no conoce.

### P9. `MODELOS_RECOMENDADOS` es código muerto con docstring que promete uso

**Qué.** `app/config.py` define `MODELOS_RECOMENDADOS` y su docstring dice "Se
usa solo como referencia en la documentación y en los mensajes de error". No se
importa en ningún sitio.

**Arreglo.** Eliminar la constante muerta y el docstring que la describe.

---

## Alcance

**Dentro.**
- `app/config.py`: nuevas settings (`llm_timeout_seconds`, `llm_max_retries`,
  `llm_max_output_tokens`), eliminar `MODELOS_RECOMENDADOS`.
- `app/services/llm_service.py`: timeout/retries en clientes, `max_tokens`,
  detección de truncamiento, `LLMServiceError`, delimitación de la transcripción.
- `app/routers/estimations.py`: `max_length` en la entrada, capturar solo
  `LLMServiceError`.
- `tests/`: actualizar + cubrir los nuevos comportamientos.
- `.env.example` y `README.md`: documentar las variables nuevas.

**Fuera.**
- **Punto 11** (derivar modelo del proveedor): los defaults actuales
  (`openai` + `gpt-4o-mini`) son coherentes, y el enunciado define `LLM_MODEL`
  como variable independiente a propósito.
- No rediseñar la arquitectura CAG.

---

## Criterios de aceptación

- [ ] Los clientes OpenAI y Anthropic se construyen con `timeout` y
      `max_retries` de `Settings`.
- [ ] `POST /api/v1/estimate` devuelve `422` con una transcripción de más de
      `50_000` caracteres, sin llamar al LLM.
- [ ] Una respuesta truncada del LLM (`finish_reason=length` /
      `stop_reason=max_tokens`) se traduce en `LLMServiceError`.
- [ ] Los fallos del proveedor se envuelven en `LLMServiceError`; un bug propio
      (`TypeError`, `KeyError`) sale como `500`, no como `502`.
- [ ] La transcripción viaja delimitada por una marca aleatoria por petición y
      las instrucciones del system prompt lo explican.
- [ ] No queda código muerto (`MODELOS_RECOMENDADOS` eliminado).
- [ ] `uv run pytest` pasa sin API keys ni tráfico real.