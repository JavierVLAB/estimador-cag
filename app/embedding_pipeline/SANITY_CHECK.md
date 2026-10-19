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
una migración de base de datos. Lo que llama la atención es la pareja C
(0.540708): dos frases genéricas de tres palabras quedan casi tan cerca como la
pareja A, que describe la misma funcionalidad con mucho más detalle. Con textos
tan cortos el modelo solo capta el dominio general (desarrollo backend), así que
la similitud no distingue bien entre "mismo tema" y "misma tarea".

## Endpoint `POST /embeddings/ingest`

Ejecutado el 2026-10-19 a las 19:31 CEST contra el contenedor reconstruido,
enviando únicamente el presupuesto `BUD-2024-001` de `data/budgets_sample.json`.

- Respuesta: HTTP 200 en 1.74 s.
- `stats`: `total_budgets=1`, `total_chunks=4`, `total_tokens=383`,
  `estimated_cost_usd=0.00000766` (383 tokens × $0.02 / 1M).
- Cada chunk trae un embedding de 1536 dimensiones con norma ≈ 1.0.

| `chunk_id` | Tokens | Complejidad | Horas |
| --- | ---: | --- | ---: |
| `BUD-2024-001::AUTH-001` | 106 | high | 120 |
| `BUD-2024-001::PSD2-002` | 96 | high | 160 |
| `BUD-2024-001::TXN-003` | 93 | medium | 140 |
| `BUD-2024-001::NOTIF-004` | 88 | low | 60 |

La metadata de cada chunk incluye `budget_id`, `component_id`, `client_sector`
(`finance`), `main_technology` (`ruby_on_rails`), `year`, `complexity` y
`estimated_hours`. El texto embebido antepone la cabecera del proyecto, por
ejemplo:

```text
[Project: Mobile banking API with OAuth 2.0 authentication and PSD2 compliance]
[Client sector: finance | Year: 2024 | Main tech: ruby_on_rails]

Component: OAuth 2.0 authentication backend
Description: Implementation of OAuth 2.0 flows (authorization code, refresh token) with JWT-based session management, multi-tenant token isolation, and rate limiting per client.
Tech stack: ruby_on_rails, postgresql, redis
Complexity: high
Estimated hours: 120
```

Similitud coseno entre los cuatro chunks del mismo presupuesto, calculada sobre
los embeddings devueltos:

| | PSD2-002 | TXN-003 | NOTIF-004 |
| --- | ---: | ---: | ---: |
| AUTH-001 | 0.9119 | 0.8849 | 0.8268 |
| PSD2-002 | | 0.8756 | 0.8310 |
| TXN-003 | | | 0.8151 |

Todas las parejas superan 0.81, muy por encima de la pareja A (0.596); incluso
notificaciones y autenticación quedan a 0.83. La hipótesis es que la cabecera de
proyecto compartida y el formato común (mismas etiquetas, mismo stack) pesan
mucho en el vector, de modo que los componentes de un presupuesto se parecen más
por su contexto que por lo que hacen. No se ha comprobado embebiendo los
componentes sin cabecera. Si se confirma, una búsqueda podría devolver
componentes del mismo presupuesto aunque no sean relevantes, y es un buen punto
para discutir en el directo junto con la estrategia de chunking.
