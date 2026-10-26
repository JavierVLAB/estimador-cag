"""Ingest every budget of the programme corpus through POST /embeddings/ingest."""

import json
import os
from pathlib import Path

import httpx

CORPUS_PATH = "data/budgets_sample.json"
DOCUMENT_TYPE = "historical_budget"
BASE_URL = os.getenv("ESTIMATOR_API_BASE_URL", "http://localhost:8000")


def main() -> int:
    """Send one request per budget; re-running reports 409 instead of duplicating."""
    budgets = json.loads(Path(CORPUS_PATH).read_text(encoding="utf-8"))
    with httpx.Client(base_url=BASE_URL, timeout=60) as client:
        for budget in budgets:
            # The corpus is a single file, so each budget is addressed by its id.
            source_path = f"{CORPUS_PATH}#{budget['budget_id']}"
            response = client.post(
                "/embeddings/ingest",
                json={
                    "source_path": source_path,
                    "document_type": DOCUMENT_TYPE,
                    "content": budget,
                },
            )
            print(f"{response.status_code} {source_path} {response.json()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
