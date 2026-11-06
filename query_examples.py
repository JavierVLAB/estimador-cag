"""Run five semantic queries against POST /search and print their top-5 chunks."""

import os

import httpx

BASE_URL = os.getenv("ESTIMATOR_API_BASE_URL", "http://localhost:8000")
K = 5
CONTENT_PREVIEW_CHARS = 120

QUERIES = [
    ("Componente directo conocido",
     "REST API development with JWT authentication for financial sector"),
    ("Reformulación semántica",
     "secure backend service with token-based access control for banking applications"),
    ("Dominio distinto",
     "mobile application for restaurant reservations"),
    ("Consulta ambigua",
     "integration with external system"),
    ("Consulta muy específica",
     "migration from monolith to microservices architecture using Kubernetes"),
]


def _preview(content: str) -> str:
    """Skip the shared project header and keep each result on one terminal line."""
    # Chunks of the same budget share the header, so it hides which component matched.
    body = content.split("\n\n", 1)[-1]
    flat = " ".join(body.split())
    return flat[:CONTENT_PREVIEW_CHARS]


def main() -> int:
    """Print query, latency and the k nearest chunks for each example query."""
    with httpx.Client(base_url=BASE_URL, timeout=60) as client:
        for number, (kind, query) in enumerate(QUERIES, start=1):
            response = client.post("/search", json={"query": query, "k": K})
            response.raise_for_status()
            payload = response.json()
            print(f"=== Query {number} · {kind}")
            print(f"    \"{query}\"  ({payload['search_time_ms']} ms)")
            for rank, result in enumerate(payload["results"], start=1):
                print(
                    f"  {rank}. chunk_id={result['chunk_id']:<4} "
                    f"distance={result['distance']:.4f} "
                    f"type={result['chunk_type']} | {_preview(result['content'])}"
                )
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
