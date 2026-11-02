# Ejercicio 09 — Diagnóstico arquitectónico del sistema RAG actual

Creado: 2026-11-02 · Estado: hecho (falta push, PR y correo)
Enunciado: `../../Curso/09_Fundamentos_RAG/00_ejercicio-diagnostico-arquitectonico-rag.md`
Rama de entrega: `session-09/pre-work`, creada desde `session-08`.
Fecha límite: lunes 2026-11-02, al final del día.

## Por qué

Al cerrar la sesión 08, el servicio sabe vectorizar los presupuestos históricos (`POST /embeddings/ingest`) y devolver los chunks más parecidos a un texto (`POST /search`). No sabe convertir una transcripción en una estimación basada en esos presupuestos. La sesión 09 construye ese flujo en el directo, y el profesor prepara la sesión a partir de los traces reales que entregamos. Sin entrega, los bloques hands-on asumen un pipeline que no habremos revisado.

## Qué cambia

Se añade al repo un documento, `arquitectura-actual.md` en la raíz, escrito sobre `examples/transcripts/TEMPLATE.md`, con estas cuatro secciones:

1. **Diagrama de la arquitectura actual.** Muestra tres capas. En el servicio IA baja un nivel (ingesta, `embedding_pipeline/`, almacenamiento y endpoints) y marca dónde acaba lo implementado.
2. **Trace anotado de `02_ambiguous.txt`.** Tiene tres pasos: embeber, buscar el top 5 y leer los chunks. Lleva comandos reproducibles, respuestas crudas y un comentario de una o dos frases por paso.
3. **Cinco fallos.** Cada uno con problema observado, causa probable y propuesta, apoyado en el trace. Si salen más, van a "Otros".
4. **Propuesta de evolución.** Un segundo diagrama con lo nuevo marcado y un párrafo de diez líneas como máximo: responsabilidad de cada módulo, dato que fluye entre ellos y la pieza más crítica.

También se añaden:
- `examples/transcripts/` con las tres transcripciones y la plantilla, traídas de la rama `session_09` del repo del curso.
- Un script cliente corto para el trace (ver Diseño).

No cambia el comportamiento del servicio.

## Fuera de alcance

- Reformulación de queries, reranking, retriever nuevo, cambios en `/search`.
- Módulo de generación y endpoints nuevos.
- Cualquier Python que vaya más allá de un script cliente para las llamadas del trace.
- Copiar una arquitectura RAG canónica en la sección 4.
- Índices vectoriales, filtros por metadata y tuning de Postgres (sigue vigente lo dicho en la sesión 08).

## Hechos del sistema que condicionan el trace (verificados en el código)

- `POST /search` recibe **texto** (`query`, `k` entre 1 y 50) y lo embebe dentro del servicio. Devuelve `chunk_id`, `document_id`, `chunk_type`, `content`, `distance` y `metadata`.
- **Ningún endpoint devuelve el vector.** Para el paso 1 hay que llamar al módulo `app/embedding_pipeline/embedder.py` desde un script. El enunciado lo permite: "con el endpoint o módulo de embeddings".
- Corpus: 15 presupuestos y 52 chunks, uno por componente, **en inglés**. Hay cuatro sectores: finance, ecommerce, healthcare e industrial. El ecommerce está en BUD-005 a 008: storefront, marketplace, grocery delivery y returns.
- La transcripción 02 está **en español**. El cliente es una tienda gourmet que pide tienda online, programa de fidelización, panel de control, pago con tarjeta y emails de pedido.
- Además del pipeline de embeddings, el servicio expone el estimador CAG de sesiones anteriores: `POST /estimate`, `/sessions`, `/sessions/{id}/estimate` y `/sessions/{id}/estimate-acb`. Este estimador recibe transcripciones y no usa `/search`.
- Frontend y backend de negocio: son `estimator-web`, la app Rails de la rama `session_06` del repo del curso, que no está copiada en este repo. Su `EstimatorAi::Client` solo llama a `/api/v1/estimate` y a `/sessions/*`, y todas esas rutas existen en nuestro servicio. Ninguna capa llama a `/embeddings/ingest` ni a `/search`, que solo se usan desde scripts.

## Hipótesis a contrastar en el trace

Son candidatos a fallo. Solo entran en la sección 3 si el trace los confirma.

- Desajuste de idioma: transcripción en español frente a un corpus en inglés.
- Un único vector para una transcripción con cinco necesidades distintas: se diluye y se queda con una o dos.
- Ruido conversacional en el vector: saludos, timestamps, nombres, anécdotas familiares.
- El top 5 por chunk mezcla componentes de presupuestos distintos, y no hay forma de agruparlos por presupuesto.
- No hay umbral: siempre devuelve 5 resultados, aunque las distancias sean altas.
- No hay puente entre `/search` y el estimador CAG: la evidencia recuperada no llega a ninguna generación.

## Criterios de aceptación

- [ ] CA1: WHEN se abre `arquitectura-actual.md` THEN tiene las cuatro secciones de la plantilla con sus encabezados → verify: `grep -c '^## [1-4]\.' arquitectura-actual.md` devuelve 4
- [ ] CA2: WHEN se lee el paso 1 del trace THEN incluye el comando exacto, la dimensión (1536), la norma, la primera y la última componente reales, y un comentario → verify: Javi
- [ ] CA3: WHEN se lee el paso 2 THEN incluye el comando exacto y la respuesta JSON cruda de `/search` con `k=5` y sus distancias → verify: volver a ejecutar el comando y comprobar que los `chunk_id` coinciden
- [ ] CA4: WHEN se lee el paso 3 THEN cada uno de los 5 chunks lleva presupuesto, sector y un juicio de relevancia → verify: Javi
- [ ] CA5: WHEN se leen los fallos THEN son cinco, cada uno con las tres líneas, y cada problema observado cita un dato del trace (chunk, distancia o texto) → verify: Javi
- [ ] CA6: WHEN se comparan los diagramas de las secciones 1 y 4 THEN lo nuevo está marcado de forma distinguible y la sección 4 no se reduce a "Query → Retrieval → Augmentation → Generation" → verify: Javi, viendo el render de Mermaid en GitHub
- [ ] CA7: WHEN se cuenta el párrafo de la sección 4 THEN tiene diez líneas o menos y nombra la pieza más crítica → verify: Javi
- [ ] CA8: WHEN se revisa el diff de la rama contra `session-08` THEN no hay cambios en `app/` → verify: `git diff --stat session-08 -- app/` vacío
- [ ] CA9: WHEN se lista la rama THEN existe `session-09/pre-work` con el documento commiteado → verify: `git log --oneline session-09/pre-work -3`

## Impacto

- Nuevos: `arquitectura-actual.md`, `examples/transcripts/*` (4 archivos), `scripts/trace_s09.py`.
- Sin cambios en `app/`, la base de datos ni las dependencias.
- Coste externo: 4 llamadas a `text-embedding-3-small`, de unos 500 a 700 tokens cada una. Unos 2.500 tokens en total: céntimos.

## Diseño

**Script del trace** (`scripts/trace_s09.py`, en inglés):
1. Lee la transcripción indicada.
2. Llama al embedder del módulo e imprime la dimensión, la norma L2, `v[0]` y `v[-1]`.
3. Hace `POST /search` con `{"query": <transcripción completa>, "k": 5}` e imprime el JSON crudo.

Se ejecuta con `docker compose run --rm -T estimator python scripts/trace_s09.py < examples/transcripts/02_ambiguous.txt`. La transcripción entra por stdin porque `examples/` no está montado en el contenedor. Con `--search-only` se salta el paso 1, y así se usa para la 01 y la 03.

Alternativa descartada: añadir un endpoint `/embeddings/encode`. El enunciado prohíbe crear endpoints nuevos.

**Diagramas:** Mermaid dentro del Markdown, porque GitHub lo renderiza. Lo implementado y lo nuevo se distinguen con `classDef` de colores distintos y con una leyenda.

## Puntos por aclarar

- Decidido (2026-11-02): el frontend y el backend de negocio se dibujan como el `estimator-web` de la sesión 6 (Rails: vistas y modelos con su propio Postgres), sin copiar su código al repo.
- Decidido (2026-11-02): el estimador CAG (`/estimate`, `/sessions`) sale en el diagrama 1, porque es lo que usa `estimator-web`, y aparece desconectado de `/search`.
- Decidido (2026-11-02): Javi autoriza 4 llamadas a la API de embeddings: el trace completo de la 02 (2 llamadas) y `/search` sobre la 01 y la 03 como contraste (2 llamadas).
- Decidido (2026-11-02): no se abre el `arquitectura-actual.md` de la rama `session_09` del repo del curso.
- Entorno verificado (2026-11-02): `/health` OK, 52 chunks de 15 documentos. Salidas crudas en `odd/s09/`.

## Tareas

## 1. Preparación
- [x] 1.1 Crear la rama `session-09/pre-work` desde `session-08` y traer `examples/transcripts/` del repo del curso → verify: `ls examples/transcripts` muestra 4 archivos
- [x] 1.2 Comprobar el entorno (lo arranca Javi) → verify: `curl -s localhost:8000/health` responde OK y `SELECT count(*) FROM chunks` devuelve 52

## 2. Trace
- [x] 2.1 Escribir `scripts/trace_s09.py` → verify: `ruff check scripts/trace_s09.py`
- [x] 2.2 Ejecutar el trace sobre `02_ambiguous.txt` y guardar la salida cruda → verify: la salida tiene dimensión 1536 y 5 resultados
- [x] 2.3 Ejecutar `/search` sobre 01 y 03 como contraste → verify: 5 resultados por transcripción
- [x] 2.4 Identificar el presupuesto y el sector de cada chunk devuelto (por `metadata` y por `data/budgets_sample.json`) → verify: los 5 chunks tienen `budget_id` y sector

## 3. Documento
- [x] 3.1 Sección 1: diagrama Mermaid de la arquitectura actual → verify: Javi
- [x] 3.2 Sección 2: trace con comandos, salidas crudas y comentarios → verify: CA2, CA3, CA4
- [x] 3.3 Sección 3: cinco fallos contrastados con el trace, más "Otros" → verify: CA5
- [x] 3.4 Sección 4: diagrama de evolución y párrafo → verify: CA6, CA7

## 4. Verificación
- [x] 4.1 Ejecutar todos los `→ verify:` de comando (CA1, CA3, CA8, CA9) y revisar el documento contra el enunciado con un subagente de contexto limpio → verify: informe criterio a criterio
- [x] 4.2 Commit en `session-09/pre-work`. El push, el PR contra `main` y el borrador del correo a george@lidr.co se preparan cuando Javi lo pida → verify: CA9

## Condición de /goal

No aplica. Es una entrega corta con la fecha límite hoy y varios criterios que solo puede juzgar Javi. Propongo ejecutarla en esta misma sesión, por tareas.
