## Context

El repositorio solo contiene documentación (`docs/ejercicio.md`), `CLAUDE.md`, `.gitignore` y `.python-version`. No hay código. El enunciado del ejercicio fija la estructura de carpetas y el flujo: recibir una transcripción, inyectar contexto estático en el prompt, llamar a un LLM y devolver la estimación.

Restricciones relevantes:

- La arquitectura es **CAG deliberada**: todo el contexto viaja en cada llamada. Sin BD, retrieval, vector store, persistencia ni caché. No es deuda técnica.
- La estructura de `app/` viene fijada por el enunciado y no se altera.
- El servidor lo arranca Javi. El agente no ejecuta procesos de larga duración ni llamadas reales al LLM.
- `.env` no se lee ni se escribe nunca.
- Prioridades declaradas: legibilidad, mantenimiento y escalado entendido como límites claros entre capas, no como puntos de extensión especulativos.

## Goals / Non-Goals

**Goals:**

- Flujo completo funcionando extremo a extremo: `POST /api/v1/estimate` → prompt con ejemplos → LLM → JSON.
- Dos proveedores (OpenAI y Anthropic) seleccionables por `LLM_PROVIDER`.
- Dependencias en una sola dirección: `routers → services → context`, con `config` como único lector del entorno.
- Poder verificar el prompt y el endpoint sin gastar llamadas al LLM.
- README que permita a alguien ajeno al proyecto entender el sistema y arrancarlo.

**Non-Goals:**

- Output estructurado (tareas y horas en campos separados). La estimación es markdown en un string.
- Abstracciones de proveedor tipo interfaz, registry o inyección de dependencias.
- Persistencia, historial de estimaciones, autenticación, rate limiting, métricas o coste.
- Optimizar la calidad de las estimaciones: eso se itera en la sesión en vivo.

## Decisions

### Selección de proveedor con un condicional, no con una abstracción

`generate_estimation` resuelve el proveedor con un `if` sobre `settings.llm_provider` y delega en una función por proveedor (`_generate_openai`, `_generate_anthropic`), ambas en `llm_service.py`.

*Alternativa descartada:* clase base `LLMProvider` con implementaciones e inyección. Con dos proveedores y una sola operación, añade indirección sin reducir complejidad, y contradice la instrucción de evitar abstracciones prematuras. Si en el futuro hay tres o cuatro proveedores con comportamientos distintos, extraer la interfaz es un refactor mecánico desde este punto.

### El prompt se construye aparte de la llamada

Dos funciones separadas en `llm_service.py`:

- `build_system_prompt(examples) -> str`: instrucciones del rol + ejemplos renderizados.
- `generate_estimation(transcription) -> EstimationResult`: construye el prompt, llama al proveedor, devuelve el resultado.

Es la pieza que más se va a iterar en la sesión en vivo, y separarla permite testearla sin red. No se crea un `prompt.py` porque el enunciado no contempla ese archivo y dos funciones cortas caben con claridad en el servicio.

### Los ejemplos se tipan, no se dejan como dicts

`app/context/examples.py` define un `dataclass` `EstimationExample(meeting_summary, estimation)` y la lista `ESTIMATION_EXAMPLES`. El enunciado los sugiere como `list[dict]`.

*Motivo:* documenta el formato en el propio tipo y evita typos silenciosos en las claves al renderizar el prompt. El coste son cuatro líneas. El módulo no importa nada del proyecto: son datos puros.

### El servicio devuelve un resultado tipado, no una tupla

`generate_estimation` devuelve un `dataclass` `EstimationResult(estimation, model, provider)`. El router lo traduce al schema Pydantic de respuesta.

*Motivo:* mantiene el servicio ignorante de FastAPI (es el límite de capa que sostiene el escalado a RAG) y hace explícito el contrato. Una tupla de tres strings se lee peor en el punto de llamada.

*Alternativa descartada:* que el servicio devuelva directamente el modelo Pydantic de respuesta HTTP. Acopla el servicio al transporte.

### Los errores del proveedor se traducen en el router

El servicio deja propagar la excepción del SDK. El router la captura y responde `502` con un mensaje fijo y sin traza. El detalle técnico va al log.

*Motivo:* el código HTTP es una decisión de transporte y pertenece al router. Mantiene el servicio reutilizable fuera de HTTP.

### Un cliente por llamada, creado dentro de la función del proveedor

No se cachean ni se reutilizan clientes a nivel de módulo.

*Motivo:* simplicidad y testabilidad — el mock intercepta el punto de creación. El coste de rendimiento es irrelevante en este ejercicio. Si molestara, mover a un singleton es trivial.

### Validación de la transcripción en el schema

`transcription` se define en el schema de request con `min_length` y validación de contenido no vacío, de forma que FastAPI devuelve `422` antes de llegar al servicio.

*Motivo:* evita gastar una llamada al LLM con entrada inútil, y deja la validación declarada junto al contrato, donde Swagger la muestra.

### Tests con el proveedor mockeado mediante monkeypatch

`tests/` con `pytest` y `TestClient` de FastAPI (requiere `httpx`). Se parchea la función del proveedor dentro de `llm_service`, no el SDK.

*Motivo:* el test verifica el contrato del endpoint y el paso de datos, no el SDK de terceros. Cobertura prevista: health, estimación correcta, transcripción inválida, fallo del proveedor → 502, y que el system prompt contiene los ejemplos.

### La configuración se instancia una vez

`config.py` expone `Settings` y una instancia `settings` de módulo, leída con `pydantic-settings` desde `.env`. Ningún otro módulo toca el entorno.

*Nota:* `LLM_MODEL` tiene default `gpt-4o-mini`, que es el modelo de OpenAI. Si se usa Anthropic hay que fijar `LLM_MODEL=claude-haiku-4-5` en el entorno. Se documenta explícitamente en `.env.example` y en el README para evitar el fallo silencioso de pedirle a Anthropic un modelo de OpenAI.

## Risks / Trade-offs

- **`LLM_MODEL` y `LLM_PROVIDER` pueden quedar descoordinados** (p.ej. `anthropic` + `gpt-4o-mini`) → se documenta en `.env.example` y README; el error del proveedor se verá como `502` con mensaje claro. No se añade validación cruzada para no inventar reglas que el enunciado no pide.
- **El contexto crece con cada ejemplo añadido** y encarece cada llamada → aceptado: es el trade-off explícito de CAG con datos pequeños, y el motivo por el que módulos posteriores pasan a RAG.
- **La calidad de la estimación depende por completo del prompt y de los ejemplos** → aceptado; el entregable es el flujo funcionando, la calidad se itera en la sesión en vivo.
- **Los tests con mock no prueban que la integración real con los SDK funcione** → mitigación: Javi hace una llamada real manual al terminar, con su `.env`. El agente no la ejecuta sin autorización.
- **Instalar los dos SDK aunque solo se use uno** engorda el entorno → aceptado a cambio de que cambiar de proveedor sea solo una variable de entorno.

## Open Questions

Ninguna bloqueante. Decidido con Javi: dos proveedores, salida markdown, tests mockeados, `.env.example` incluido, README con versión 1.0 orientado a alguien que no conoce el proyecto.
