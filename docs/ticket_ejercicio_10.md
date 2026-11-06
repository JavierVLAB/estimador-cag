# Ejercicio 10 — Búsqueda híbrida y reranking, medidos

Creado: 2026-11-06 · Estado: en curso
Enunciado: `docs/ejercicio_10.md` (copia de `../../Curso/10_Tecnicas_recuperacion/00_ejercicio-tecnicas-avanzadas-recuperacion.md`)
Teoría: lecciones 01 (reranking), 02 (medición) y 03 (búsqueda híbrida) del módulo 10.
Rama de entrega: `session-10/pre-work`, creada desde `session-09/pre-work`.
Fecha límite: lunes 2026-11-09, al final del día.

## Por qué

`POST /search` ordena los chunks solo por distancia coseno. En el trace del ejercicio 09, la consulta de una tienda online recuperó componentes de presupuestos de pagos y de otros sectores: estaban cerca en el espacio vectorial, pero no servían para estimar. El ejercicio 10 prueba dos remedios, la búsqueda híbrida (léxica + vectorial fusionadas con RRF) y el reranking con cross-encoder, y pide demostrar con números cuánto mejoran la precisión y cuánto cuestan en latencia. El profesor prepara la sesión en vivo con las cifras que entreguemos.

## Qué cambia

1. **Columna full-text.** Una migración Alembic `0002` añade a `chunks` una columna `content_tsv` (`tsvector` generada a partir de `content`) y un índice GIN.
2. **Rama léxica y RRF.** Una búsqueda por palabras clave sobre `content_tsv`, ordenada por `ts_rank`, y una función de fusión RRF con la constante `k` configurable (por defecto 60). La búsqueda híbrida devuelve un único ranking fusionado.
3. **Reranker.** El wrapper `CrossEncoderReranker` y su script de verificación, traídos de la rama `session_10` del repo del curso. Se integra con el patrón recall-then-rerank: recupera 50 candidatos y deja los 5 mejores.
4. **`POST /search` con modo y reranking.** El request admite `mode` (`vector` | `hybrid`) y `rerank` (bool). Si no se envían, se usan los valores de configuración (`SEARCH_MODE`, `RERANK_ENABLED`). Los valores por defecto (`vector`, `false`) mantienen el comportamiento actual. Así se activa o desactiva el reranking sin tocar código.
5. **Golden set y medición.** `evals/retrieval/golden_set.json` con 5 consultas anotadas a mano, y `scripts/measure_retrieval.py`, que ejecuta las configuraciones A, B, C y D y escribe la tabla de precision@5 y latencia.
6. **Resultados.** `docs/resultados_ejercicio_10.md` con la tabla comparativa, el detalle por consulta y el párrafo de conclusiones.

Todo el código (nombres, comentarios, logs) va en inglés, como pide el enunciado.

## Fuera de alcance

- Expansión o descomposición de consultas, routing multi-índice y filtrado por metadatos o por fecha (se hacen en el directo).
- Índices vectoriales (HNSW, IVFFlat) y tuning de Postgres: la búsqueda vectorial sigue siendo exacta.
- Pipeline de generación (reformulación y estimación con LLM): el ejercicio mide la recuperación.
- El resto de piezas de la rama `session_10` del curso (`fusion.py`, `pipeline.py`, migración FTS, golden set): las escribimos nosotros.

## Hechos que condicionan el diseño (verificados)

- **El corpus está en inglés.** Los 15 presupuestos de `data/budgets_sample.json` tienen sus textos en inglés. El enunciado habla de presupuestos en español porque su dataset es otro.
- **El corpus es pequeño:** 52 chunks, uno por componente. Recuperar 50 candidatos equivale a recuperar casi todo el corpus, así que en C y D el reranker reordena prácticamente todo y la rama de recall apenas influye.
- **No hay pipeline RAG de generación en este repo**, solo `/search`. El enunciado lo da por hecho, pero la medición solo necesita la recuperación.
- **La rama `session_10` del curso** trae el wrapper (`app/generation/rag/retrieval/reranker.py`), `verify_reranker.py` y la dependencia `sentence-transformers>=3.0`, que arrastra `torch`. El modelo es `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, multilingüe y pensado para CPU. Se carga en diferido, la primera vez que se reranquea.
- **`websearch_to_tsquery`**, el que usa la lección 03, une los términos con AND. Con una descripción de proyecto de 15 palabras, casi ningún chunk contiene todas, y la rama léxica volvería vacía.

## Decisiones (propuestas, pendientes de aprobar)

- **D1. Copiar del curso solo el wrapper y el script de verificación.** El enunciado dice que no hay que implementar el reranker, solo integrarlo. Van a `app/retrieval/reranker.py` y `app/retrieval/verify_reranker.py`, junto al resto de la recuperación nueva.
- **D2. Añadir `sentence-transformers` como dependencia.** Sin ella no hay reranker. Coste: la imagen Docker crece bastante por `torch` y la primera carga descarga el modelo de Hugging Face (unos cientos de MB) a una caché en un volumen. El reranking corre en local: ningún dato sale de la máquina.
- **D3. Configuración `'english'` en el `tsvector` y en la consulta**, porque el corpus está en inglés. Con `'spanish'` el stemming y las stopwords estarían mal para este corpus.
- **D4. Consulta léxica con OR.** La rama léxica convierte la consulta en lexemas con `plainto_tsquery('english', …)` y los une con `|`. `ts_rank` premia a los chunks que contienen más términos.
- **D5. Golden set en inglés.** Si las consultas van en español sobre un corpus en inglés, la rama léxica no encuentra nada y la comparación A/B no mide la técnica. El cruce de idioma queda como observación en las conclusiones.
- **D6. precision@5 como en la lección 02.** Cada uno de los 5 primeros chunks se mapea a su `budget_id` y cuenta como acierto si ese presupuesto está anotado como relevante. Si dos chunks del mismo presupuesto relevante aparecen, cuentan los dos. Se informa también recall@5 a nivel de presupuesto, porque sale gratis.
- **D7. Latencia.** Cada configuración se ejecuta 3 veces por consulta y se informa la mediana. El embedding de cada consulta se calcula una vez y se reutiliza en las cuatro configuraciones: es igual para todas y su latencia, que depende de la red, se mide aparte. Antes de medir se calienta el modelo del reranker. La medición se hace dentro del proceso, sin HTTP.
- **D8. Golden set anotado antes de ver resultados.** El agente propone las 5 consultas y los presupuestos relevantes de cada una con un criterio escrito. Javi los revisa y aprueba antes de lanzar la medición.

## Criterios de aceptación

- [ ] CA1: WHEN se aplica la migración THEN `chunks` tiene `content_tsv` generada con `'english'` y un índice GIN → verify: `docker compose exec estimator alembic upgrade head` y `\d chunks` en `estimator-postgres`
- [ ] CA2: WHEN se hace `alembic downgrade -1` THEN la columna y el índice desaparecen sin tocar los datos → verify: `alembic downgrade -1 && alembic upgrade head` y `SELECT count(*) FROM chunks` sigue en 52
- [ ] CA3: WHEN se fusionan dos rankings con RRF THEN el orden coincide con el ejemplo de la lección 03 (el consenso adelanta al campeón de una sola lista) y `k` se puede cambiar → verify: `pytest tests/test_retrieval_fusion.py`
- [ ] CA4: WHEN se busca en modo `hybrid` una consulta de varias palabras THEN la rama léxica devuelve resultados y el ranking final no tiene chunks repetidos → verify: `pytest tests/test_retrieval_search.py` y una llamada real a `/search` con `mode=hybrid`
- [ ] CA5: WHEN `rerank=true` THEN se recuperan 50 candidatos, el reranker los reordena y se devuelven 5; WHEN `rerank=false` THEN no se carga el modelo → verify: `pytest tests/test_retrieval_search.py` con un reranker falso
- [ ] CA6: WHEN se llama a `/search` sin `mode` ni `rerank` THEN la respuesta es la misma que antes del cambio → verify: `pytest tests/test_embedding_pipeline.py` sin modificar sus casos de `/search`
- [ ] CA7: WHEN se ejecuta la verificación del reranker THEN el modelo se descarga, carga y puntúa el documento relevante por encima → verify: `docker compose exec estimator python -m app.retrieval.verify_reranker` termina con código 0
- [ ] CA8: WHEN se abre el golden set THEN tiene 5 consultas, cada una con sus presupuestos relevantes y el criterio de anotación → verify: Javi
- [ ] CA9: WHEN se ejecuta `scripts/measure_retrieval.py` THEN imprime y guarda la tabla A/B/C/D con precision@5 media, recall@5 y latencia mediana, y el detalle por consulta → verify: `docker compose exec estimator python scripts/measure_retrieval.py`
- [ ] CA10: WHEN se lee `docs/resultados_ejercicio_10.md` THEN tiene la tabla de CA9 copiada de la salida real y un párrafo breve que dice qué configuración usar y si el reranking compensa su latencia → verify: Javi
- [ ] CA11: WHEN se revisa el diff THEN no hay índices vectoriales, filtros por metadata, expansión de consultas ni routing → verify: `git diff session-09/pre-work --stat` y revisión del diff
- [ ] CA12: WHEN se pasa la suite THEN todos los tests y ruff pasan → verify: `docker compose exec estimator pytest` y `ruff check .`

## Impacto

- Nuevos: `alembic/versions/0002_chunks_fulltext.py`, `app/retrieval/` (`fusion.py`, `search.py`, `reranker.py`, `verify_reranker.py`), `evals/retrieval/golden_set.json`, `scripts/measure_retrieval.py`, `docs/resultados_ejercicio_10.md`, tests nuevos.
- Modificados: `app/embedding_pipeline/router.py` y `schemas.py` (`/search` delega en `app/retrieval/search.py`), `app/embedding_pipeline/models.py` (columna `content_tsv`), `app/config.py` (`SEARCH_MODE`, `RERANK_ENABLED`, `RERANKER_MODEL`, `RRF_K`), `pyproject.toml` y `uv.lock`, `docker-compose.yml` (volumen para la caché del modelo y montaje de `evals/`), `README.md` (sección breve de cómo medir).
- Dependencia nueva: `sentence-transformers` (con `torch`).
- Coste externo: unas 10 llamadas a `text-embedding-3-small` (5 consultas del golden set y pruebas). Céntimos. Requieren autorización explícita antes de ejecutarse.

## Diseño

**Flujo de `/search`:**

1. Embeber la consulta (como hoy).
2. Recall: si `rerank`, `limit = 50`; si no, `limit = k`.
   - `vector`: top-`limit` por `cosine_distance`.
   - `hybrid`: top-50 vectorial y top-50 léxico, fusión RRF y corte en `limit`.
3. Si `rerank`, el cross-encoder puntúa los candidatos y se queda con `k`.
4. La respuesta mantiene su forma actual. `distance` sigue informando la distancia coseno de cada chunk, y se añaden `rrf_score` y `rerank_score` cuando aplican.

**Riesgos:**

- La imagen con `torch` tarda en construirse y ocupa mucho → `torch` CPU y caché del modelo en un volumen, para descargarlo una sola vez.
- El reranker es síncrono y tarda cientos de ms → se ejecuta en `run_in_threadpool`, como el embedder.
- Con 52 chunks, C y D casi coinciden → se dice en las conclusiones; es un resultado del corpus, no un fallo de la medición.

## Tareas

### 1. Base
- [x] 1.1 Crear la rama `session-10/pre-work` desde `session-09/pre-work` → verify: `git branch --show-current`
- [x] 1.2 Añadir `sentence-transformers`, ajustar Dockerfile y `docker-compose.yml` (volumen de caché, montaje de `evals/`) → verify: Javi reconstruye la imagen y `docker compose exec estimator python -c "import sentence_transformers"`
- [x] 1.3 Traer el wrapper y `verify_reranker.py` a `app/retrieval/`, con `RERANKER_MODEL` en `app/config.py` → verify: CA7

### 2. Datos
- [x] 2.1 Migración `0002` con `content_tsv` y el índice GIN, y la columna en el modelo ORM → verify: CA1, CA2

### 3. Lógica
- [x] 3.1 [P] `app/retrieval/fusion.py` con RRF y sus tests → verify: CA3
- [x] 3.2 `app/retrieval/search.py`: ramas vectorial y léxica, híbrida y recall-then-rerank, con tests → verify: CA4, CA5
- [ ] 3.3 `/search` con `mode` y `rerank`, y valores por defecto de configuración → verify: CA6, llamada real con las cuatro combinaciones

### 4. Medición
- [ ] 4.1 Proponer el golden set (5 consultas, presupuestos relevantes, criterio) y esperar la aprobación de Javi → verify: CA8
- [ ] 4.2 `scripts/measure_retrieval.py` con precision@5, recall@5 y latencia mediana, con test de las métricas → verify: `pytest tests/test_retrieval_metrics.py`
- [ ] 4.3 Ejecutar la medición (con autorización para las llamadas de embeddings) y guardar la salida cruda en `odd/s10/` → verify: CA9

### 5. Documentación
- [ ] 5.1 `docs/resultados_ejercicio_10.md` con la tabla, el detalle y las conclusiones → verify: CA10
- [ ] 5.2 Sección breve en el README: cómo verificar el reranker y cómo lanzar la medición → verify: Javi

### 6. Verificación
- [ ] 6.1 Ejecutar todos los `→ verify:` y revisar el diff contra el alcance → verify: CA11, CA12

## Condición de /goal

Todas las tareas marcadas, cada `→ verify:` ejecutable pasando, ruff y pytest en verde, `/search` sin parámetros nuevos igual que antes, y nada fuera del alcance tocado. La tarea 4.1 se detiene a esperar a Javi. O parar tras 40 turnos.

`/goal Implement docs/ticket_ejercicio_10.md task by task until <condición>, or stop after 40 turns`
