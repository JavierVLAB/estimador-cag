"""Trace a raw transcript through the current system: embed it and run POST /search.

Reads the transcript from stdin, because examples/ is not mounted in the container:
    docker compose run --rm -T estimator python scripts/trace_s09.py < examples/transcripts/02_ambiguous.txt
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path

import httpx

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.dependencies import get_openai_client
from app.embedding_pipeline.embedder import OpenAIEmbedder

BASE_URL = os.getenv("ESTIMATOR_API_BASE_URL", "http://localhost:8000")


def main() -> int:
    """Print the transcript vector summary (step 1) and the raw /search response (step 2)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--search-only", action="store_true", help="Skip step 1 (no vector)")
    args = parser.parse_args()

    transcript = sys.stdin.read()

    if not args.search_only:
        vector = OpenAIEmbedder(get_openai_client()).embed_one(transcript)
        print("=== Step 1 · embedding")
        print(json.dumps({
            "dimension": len(vector),
            "l2_norm": math.sqrt(sum(value * value for value in vector)),
            "first_component": vector[0],
            "last_component": vector[-1],
        }, indent=2))

    response = httpx.post(f"{BASE_URL}/search", json={"query": transcript, "k": args.k}, timeout=60)
    response.raise_for_status()
    print("=== Step 2 · POST /search")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
