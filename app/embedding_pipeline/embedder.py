"""OpenAI adapter for the in-memory budget embedding pipeline."""

from collections.abc import Callable
from time import perf_counter, sleep as default_sleep
from typing import Any

import structlog
from openai import RateLimitError

from app.embedding_pipeline.chunker import EMBEDDING_MODEL
from app.embedding_pipeline.schemas import Chunk, EmbeddedChunk

MAX_BATCH_SIZE = 100
INPUT_TOKEN_COST_PER_MILLION_USD = 0.02
RATE_LIMIT_RETRY_DELAYS_SECONDS = (1, 2, 4)

log = structlog.get_logger()


class OpenAIEmbedder:
    """Embed chunks in bounded batches while preserving their original order."""

    def __init__(
        self,
        client: Any | None,
        *,
        model: str = EMBEDDING_MODEL,
        sleep: Callable[[float], None] = default_sleep,
        rate_limit_error: type[Exception] = RateLimitError,
    ) -> None:
        self._client = client
        self._model = model
        self._sleep = sleep
        self._rate_limit_error = rate_limit_error

    def embed_many(self, chunks: list[Chunk]) -> list[EmbeddedChunk]:
        """Return provider vectors paired with their original chunk data."""
        if self._client is None:
            raise RuntimeError("OpenAI embedding client is not configured")

        embedded_chunks: list[EmbeddedChunk] = []
        for start in range(0, len(chunks), MAX_BATCH_SIZE):
            batch = chunks[start : start + MAX_BATCH_SIZE]
            started_at = perf_counter()
            response = self._create_embeddings([chunk.text for chunk in batch])
            vectors = self._vectors_in_input_order(response)
            if len(vectors) != len(batch):
                raise RuntimeError("OpenAI returned an embedding count that does not match the batch")
            embedded_chunks.extend(
                EmbeddedChunk(**chunk.model_dump(), embedding=vector)
                for chunk, vector in zip(batch, vectors, strict=True)
            )
            log.info(
                "embedding_batch_processed",
                chunk_count=len(batch),
                total_tokens=sum(chunk.token_count for chunk in batch),
                latency_ms=round((perf_counter() - started_at) * 1000, 2),
            )
        return embedded_chunks

    def embed(self, chunks: list[Chunk]) -> list[EmbeddedChunk]:
        """Backward-compatible alias for embedding structured chunks."""
        return self.embed_many(chunks)

    def embed_one(self, text: str) -> list[float]:
        """Return the provider vector for one standalone text input."""
        if self._client is None:
            raise RuntimeError("OpenAI embedding client is not configured")

        vectors = self._vectors_in_input_order(self._create_embeddings([text]))
        if len(vectors) != 1:
            raise RuntimeError("OpenAI returned an embedding count that does not match the input")
        return vectors[0]

    @staticmethod
    def estimate_cost_usd(total_tokens: int) -> float:
        """Estimate input cost using the labelled current embedding price."""
        return total_tokens * INPUT_TOKEN_COST_PER_MILLION_USD / 1_000_000

    def _create_embeddings(self, texts: list[str]) -> Any:
        for delay in (*RATE_LIMIT_RETRY_DELAYS_SECONDS, None):
            try:
                return self._client.embeddings.create(model=self._model, input=texts)
            except self._rate_limit_error:
                if delay is None:
                    raise
                self._sleep(delay)
        raise AssertionError("unreachable")

    @staticmethod
    def _vectors_in_input_order(response: Any) -> list[list[float]]:
        return [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
