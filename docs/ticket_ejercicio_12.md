# Ejercicio 12 — Agente de estimación con bucle manual

Creado: 2026-11-23 · Estado: en curso
Enunciado: `docs/ejercicio_12.md` (copia de `../../Curso/12_Agentes_IA/00_ejercicio-introduccion-agentes-ia.md`)
Teoría: lecciones 01 a 06 del módulo 12.
Rama de entrega: `session-12/pre-work`, creada desde `session-10/pre-work`. El ejercicio 11 no se entrega.
Fecha límite: lunes 2026-11-23, al final del día.

## Por qué

El pipeline fijo hace una sola búsqueda por petición. Una transcripción que mezcla piezas independientes (backend, integración con ERP, app móvil, analítica) necesita una búsqueda por componente, estimaciones parciales y una consolidación, y el número de pasos depende de la transcripción. El ejercicio construye esa capa agéntica sin framework, con el bucle conducido a mano para poder capturar y mostrar cada decisión del modelo.

## Qué cambia

1. **Módulo `app/agent/`** en el servicio IA:
   - `tools.py`: los schemas planos de la Responses API con `strict: true` y sus implementaciones.
     - `search_budgets(query, filters)` envuelve `app.retrieval.search.search` en modo `hybrid` sin reranking, la mejor configuración del ejercicio 10. Devuelve, por chunk, el `budget_id`, el componente, el sector, el año, la complejidad, las horas y un extracto. `filters.sector` es opcional (valor nulo) y se aplica sobre los candidatos recuperados.
     - `calculate_estimate(components)` es determinista, a partir del esqueleto del curso: mediana de las horas de referencia más un 15 % de contingencia. Un componente sin referencias queda a 0 h y marcado como `unbudgeted`.
     - Ambas tools piden un argumento `reason` con el motivo de la llamada, que alimenta la traza aunque la API no devuelva resúmenes de razonamiento.
   - `loop.py`: el bucle manual sobre `client.responses.create`, encadenado con `previous_response_id`, con `reasoning={"effort": ..., "summary": "auto"}` y un máximo de iteraciones. La respuesta final se pide con un JSON Schema estricto (`text.format`) y se valida con Pydantic.
   - `schemas.py`: la estimación final, los pasos de la traza y el resultado del agente.
2. **Script `scripts/run_agent.py <transcripción>`** con `--model`, `--effort` y `--out`. Imprime la traza con el formato del enunciado (`STEP n` / `reasoning` / `action` / `observation`) y la estimación final, y la guarda en un fichero.
3. **Material del curso** en `data/session_12/`: las dos transcripciones de ejemplo.
4. **Trazas** en `odd/s12/`: la de la transcripción simple con `gpt-5-mini` y la entregable de la compleja con `gpt-5` y esfuerzo `medium`.

Todo el código (nombres, descripciones, prompts, logs) va en inglés.

## Fuera de alcance

- La tool opcional `validate_estimate`.
- Endpoint HTTP para el agente y cambios en `POST /estimate`.
- Reranking dentro de `search_budgets` y cambios en la recuperación.
- Ejercicio 11 (citación por línea y RAGAS).

## Hechos que condicionan el diseño (verificados)

- **Corpus en inglés y transcripciones en español.** La descripción de `search_budgets` pide la `query` en inglés; si no, la rama léxica de la búsqueda híbrida no encuentra nada.
- **El corpus no tiene sector logístico ni integraciones con SAP.** Sectores: `finance`, `ecommerce`, `healthcare` e `industrial`; años 2023 y 2024. En la transcripción compleja se espera que algún componente quede sin referencia o con referencias aproximadas.
- **Cada chunk es un componente** y lleva `estimated_hours` en su metadata.
- **Con `strict: true` todos los parámetros son obligatorios**: lo opcional se expresa con tipos que admiten `null`.

## Criterios de aceptación

- [x] CA1: WHEN se definen las tools THEN son schemas planos (`type`, `name`, `description`, `parameters` al mismo nivel) con `strict: true` y todos los campos en `required` → verify: `pytest tests/test_agent_tools.py`
- [x] CA2: WHEN `calculate_estimate` recibe componentes con y sin referencias THEN devuelve la mediana más el 15 %, 0 h y `unbudgeted=True` para los vacíos, y el total → verify: `pytest tests/test_agent_tools.py`
- [x] CA3: WHEN el modelo devuelve `function_call` THEN el bucle ejecuta cada tool, devuelve un `function_call_output` con el mismo `call_id`, encadena con `previous_response_id` y registra razonamiento, acción y observación → verify: `pytest tests/test_agent_loop.py` con un cliente falso
- [x] CA4: WHEN se alcanza el máximo de iteraciones THEN el bucle para y lo indica en el resultado → verify: `pytest tests/test_agent_loop.py`
- [x] CA5: WHEN se ejecuta el agente con la transcripción simple y `gpt-5-mini` THEN termina por sí solo con una estimación → verify: `docker compose run --rm -v ./odd:/app/odd estimator python -m scripts.run_agent data/session_12/sample_transcript_simple.txt --model gpt-5-mini --out odd/s12/trace_simple.txt`
- [x] CA6: WHEN se ejecuta con la transcripción compleja, `gpt-5` y esfuerzo `medium` THEN identifica más de un componente, llama más de una vez a `search_budgets`, llama a `calculate_estimate`, termina solo y la traza muestra razonamiento, acción y observación en cada paso → verify: mismo comando con `sample_transcript_complex.txt --model gpt-5 --effort medium --out odd/s12/trace_complex.txt`, y lectura de la traza
- [ ] CA7: WHEN se lee la estimación final THEN es coherente con el último `calculate_estimate` (componentes y total) → verify: Javi

## Impacto

- Nuevos: `app/agent/`, `scripts/run_agent.py`, `data/session_12/`, `tests/test_agent_tools.py`, `tests/test_agent_loop.py`, `odd/s12/`.
- Sin cambios en dependencias: `openai` 2.24 ya trae la Responses API.
- Llamadas reales a OpenAI solo en CA5 y CA6, con autorización de Javi. Coste estimado por el curso: menos de un par de dólares.

## Tareas

## 1. Tools
- [x] 1.1 Schemas de las tools y `calculate_estimate` en `app/agent/tools.py`, con tests → verify: `pytest tests/test_agent_tools.py`
- [x] 1.2 `search_budgets` envolviendo `search()`, con test sobre la sesión falsa → verify: `pytest tests/test_agent_tools.py`
## 2. Bucle
- [x] 2.1 Schemas de resultado y traza en `app/agent/schemas.py`; bucle en `app/agent/loop.py`, con tests → verify: `pytest tests/test_agent_loop.py`
## 3. Script y material
- [x] 3.1 Copiar las transcripciones a `data/session_12/` y escribir `scripts/run_agent.py` → verify: `ruff check app/agent scripts/run_agent.py`
## 4. Verificación
- [x] 4.1 Suite completa y lint → verify: `pytest` y `ruff check .`
- [x] 4.2 Ejecución con la transcripción simple (CA5), con autorización de Javi
- [x] 4.3 Ejecución entregable con la compleja (CA6) y revisión de la traza (CA7)

## Resultado (2026-11-23)

- **Transcripción simple, `gpt-5-mini`** (`odd/s12/trace_simple.txt`): 3 turnos, 1 búsqueda y 1 cálculo. Un componente con referencia BUD-2024-001 (120 h): 138 h en total. En la primera ejecución el agente partió el único componente en cinco subtareas y contó cinco veces la misma referencia (690 h). El prompt se corrigió para que los componentes sean entregables independientes y para que una referencia histórica no respalde más de un componente.
- **Transcripción compleja, `gpt-5` con esfuerzo `medium`** (`odd/s12/trace_complex.txt`): 10 turnos, 8 búsquedas (con reformulación en el backend, SAP y la app móvil) y 1 cálculo. Cuatro componentes; el total, 368 h, coincide con el último `calculate_estimate`. La integración con SAP y la app móvil quedan marcadas como `unbudgeted`, porque el corpus no tiene integraciones ERP ni apps móviles: el total infraestima el proyecto y así lo recogen los supuestos de la estimación.
- El agente hizo las búsquedas en serie, una por turno. Con 10 turnos quedó cerca del máximo de 12.
