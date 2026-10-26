# estimador-cag — ejercicios del curso (sesión 08 en curso)

## Base del código

El código de la raíz **no es nuestro en origen**: es el `estimator/` de la rama `session_06` del repo del curso, copiado a la raíz. Nuestro estimador propio hasta la sesión 5 vive en la rama `pre-session-05`.

Sobre esa base implementamos el ejercicio 07 (pipeline de embeddings en memoria):

* `app/embedding_pipeline/`: chunker estructural (1 chunk por componente), embedder OpenAI (`text-embedding-3-small`, 1536d) y `POST /embeddings/ingest`.
* `scripts/compare.py`: sanity check de similitud coseno.
* `data/budgets_sample.json`: corpus del programa, 15 presupuestos y 52 componentes.
* Evidencias en `app/embedding_pipeline/SANITY_CHECK.md` y `odd/`; change de OpenSpec en `openspec/changes/exercise-07-embeddings/`.

## Ejercicio actual: 08, migración a pgvector + `/search`

Antes de proponer cambios, leer `docs/ejercicio_08.md` (copia del enunciado del curso). El enunciado define el alcance. La teoría del módulo está en `../../Curso/08_BBDD_vectoriales/` (lecciones 01 a 05).

Entregable: Postgres + pgvector en `docker-compose`, migración Alembic (extensión, `documents`, `chunks`, índices no vectoriales), `POST /embeddings/ingest` que persiste en una transacción con 409 por duplicado, `POST /search` con `cosine_distance`, `query_examples.py`, `output_examples.txt` y una sección del README de una página como máximo.

**Fuera de alcance** (se hace en el directo, adelantarlo invalida las mediciones): índices vectoriales (HNSW, IVFFlat), filtros por metadata en `/search`, búsqueda híbrida y tuning de Postgres. Todo con valores por defecto.

## Diferencias con el enunciado y el README

* El enunciado llama `ai_service` al servicio de la API. Aquí se llama `estimator`: los comandos son `docker compose run --rm estimator ...`.
* El enunciado espera un presupuesto por petición (`source_path`, `document_type`, `content`). Nuestro corpus es un único JSON con 15 presupuestos.
* El `README.md` es el original del curso y dice `cd estimator`. Aquí el código está en la raíz, así que ese paso sobra.

## Repo de referencia del curso

`https://github.com/LIDR-academy-temp/ai-engineering` (el `LIDR-academy/ai-engineering` del enunciado no es accesible). Sus ramas `session_07` y `session_08` han evolucionado respecto a nuestra base: ya traen Postgres, Alembic y, en `session_08`, una solución del ejercicio 08 de otra edición con una estructura de carpetas distinta. Usarla como consulta solo cuando Javi lo decida.

## Límites operativos

* El servidor y `docker compose` los arranca Javi, no el agente.
* Nunca leer ni escribir `.env`.
* No hacer llamadas reales a un LLM ni a la API de embeddings sin autorización explícita. La ingesta del corpus y `query_examples.py` las hacen.
* No instalar, eliminar o actualizar dependencias sin discutirlo antes.
