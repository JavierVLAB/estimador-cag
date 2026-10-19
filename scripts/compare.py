"""Compare the semantic similarity of two texts with the shared embedder."""

import argparse
import math
from collections.abc import Sequence

from app.dependencies import get_openai_client
from app.embedding_pipeline.embedder import OpenAIEmbedder


def cosine_similarity(vector_a: Sequence[float], vector_b: Sequence[float]) -> float:
    """Calculate cosine similarity without numerical-computing dependencies."""
    if len(vector_a) != len(vector_b):
        raise ValueError("Embedding vectors must have the same dimension")

    magnitude_a = math.sqrt(sum(value * value for value in vector_a))
    magnitude_b = math.sqrt(sum(value * value for value in vector_b))
    if magnitude_a == 0 or magnitude_b == 0:
        raise ValueError("Embedding vectors must have non-zero magnitude")
    return sum(a * b for a, b in zip(vector_a, vector_b, strict=True)) / (magnitude_a * magnitude_b)


def build_embedder() -> OpenAIEmbedder:
    """Create the same OpenAI adapter used by the HTTP ingestion boundary."""
    return OpenAIEmbedder(get_openai_client())


def main(argv: Sequence[str] | None = None, *, embedder: OpenAIEmbedder | None = None) -> int:
    """Parse two texts, embed them, and print their cosine similarity."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text-a", required=True, help="First text to compare")
    parser.add_argument("--text-b", required=True, help="Second text to compare")
    args = parser.parse_args(argv)

    active_embedder = embedder or build_embedder()
    similarity = cosine_similarity(
        active_embedder.embed_one(args.text_a), active_embedder.embed_one(args.text_b)
    )
    print(f"Text A: {args.text_a}")
    print(f"Text B: {args.text_b}")
    print(f"Cosine similarity: {similarity:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
