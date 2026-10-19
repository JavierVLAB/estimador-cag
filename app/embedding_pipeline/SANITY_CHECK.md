# Sanity check de embeddings

Ejecutado el 2026-10-19 a las 19:07 CEST con `uv run python -m scripts.compare`
usando la credencial local configurada en `.env` y el modelo
`text-embedding-3-small`.

| Pareja | Texto A | Texto B | Similitud coseno |
| --- | --- | --- | ---: |
| A (cercanos) | OAuth 2.0 authentication backend with JWT tokens for fintech mobile app | Authorization service using JSON Web Tokens for a banking application | 0.595734 |
| B (no relacionados) | OAuth 2.0 authentication backend with JWT tokens for fintech mobile app | Database migration from MySQL to PostgreSQL with zero downtime | 0.191966 |
| C (genéricos) | Backend services | API development | 0.540708 |

La pareja A obtuvo una similitud media-alta (0.595734), cercana a la expectativa
orientativa de textos semánticamente próximos, aunque no supera 0.6. La pareja B
es claramente menor (0.191966), por lo que el modelo distingue la autenticación de
una migración de base de datos. La pareja C muestra una similitud alta (0.540708):
al ser frases genéricas de desarrollo backend, comparten contexto amplio aunque
no describen la misma tarea concreta.

El endpoint se verificó manualmente desde Swagger (`/docs`) con el presupuesto
`BUD-2024-001`: respondió cuatro chunks contextualizados y sus embeddings.
