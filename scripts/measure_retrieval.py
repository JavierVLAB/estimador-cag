"""Measure configurations A-D against the hand-annotated retrieval golden set.

    docker compose run --rm -v ./evals:/app/evals estimator python -m scripts.measure_retrieval

Each query is embedded once and the vector is reused by every configuration: the
embedding call is identical for all of them and its latency depends on the
network, so it is reported separately. The reranker is loaded and warmed up
before timing. Latency is measured in-process (no HTTP) over REPETITIONS runs.
"""

import asyncio
import json
import statistics
import sys
from pathlib import Path
from time import perf_counter

from app.config import get_settings
from app.dependencies import get_openai_client
from app.embedding_pipeline.database import get_sessionmaker
from app.embedding_pipeline.embedder import OpenAIEmbedder
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.search import search

GOLDEN_SET_PATH = Path("evals/retrieval/golden_set.json")
REPETITIONS = 3
CONFIGURATIONS = [
    ("A", "vector", False),
    ("B", "hybrid", False),
    ("C", "vector", True),
    ("D", "hybrid", True),
]


def precision_at_k(retrieved_budget_ids: list[str], relevant: set[str], k: int) -> float:
    """Fraction of the top-k chunks whose budget is relevant (duplicates count)."""
    top = retrieved_budget_ids[:k]
    return sum(budget_id in relevant for budget_id in top) / k


def recall_at_k(retrieved_budget_ids: list[str], relevant: set[str], k: int) -> float:
    """Fraction of the relevant budgets that appear at least once in the top-k."""
    return len(set(retrieved_budget_ids[:k]) & relevant) / len(relevant)


async def run(golden: dict) -> str:
    settings = get_settings()
    k = golden["k"]
    queries = golden["queries"]
    embedder = OpenAIEmbedder(get_openai_client())
    reranker = CrossEncoderReranker.from_settings()
    reranker.load()
    reranker.score("warm up", ["first pass allocates the model buffers"])

    embed_ms: list[float] = []
    vectors: dict[str, list[float]] = {}
    for entry in queries:
        started = perf_counter()
        vectors[entry["id"]] = embedder.embed_one(entry["query"])
        embed_ms.append((perf_counter() - started) * 1000)

    lines: list[str] = []
    summary: list[str] = []
    async with get_sessionmaker()() as session:
        for name, mode, rerank in CONFIGURATIONS:
            precisions, recalls, latencies = [], [], []
            lines.append(f"\n### {name}: mode={mode}, rerank={rerank}\n")
            lines.append("| Query | P@5 | R@5 | Median ms | Top-5 budgets |")
            lines.append("|---|---|---|---|---|")
            for entry in queries:
                relevant = set(entry["relevant_budget_ids"])
                runs = []
                for _ in range(REPETITIONS):
                    started = perf_counter()
                    chunks = await search(
                        session,
                        entry["query"],
                        vectors[entry["id"]],
                        k=k,
                        mode=mode,
                        reranker=reranker if rerank else None,
                        recall_k=settings.RETRIEVAL_RECALL_K,
                        rrf_k=settings.RRF_K,
                    )
                    runs.append((perf_counter() - started) * 1000)
                budget_ids = [chunk.metadata_["budget_id"] for chunk in chunks]
                precision = precision_at_k(budget_ids, relevant, k)
                recall = recall_at_k(budget_ids, relevant, k)
                precisions.append(precision)
                recalls.append(recall)
                latencies.extend(runs)
                marked = ", ".join(
                    f"**{b[-3:]}**" if b in relevant else b[-3:] for b in budget_ids
                )
                lines.append(
                    f"| {entry['id']} | {precision:.2f} | {recall:.2f} "
                    f"| {statistics.median(runs):.1f} | {marked} |"
                )
            summary.append(
                f"| {name} | {'Hybrid' if mode == 'hybrid' else 'Vector'} "
                f"| {'Yes' if rerank else 'No'} | {statistics.mean(precisions):.2f} "
                f"| {statistics.mean(recalls):.2f} | {statistics.median(latencies):.1f} "
                f"| {max(latencies):.1f} |"
            )

    header = [
        f"Golden set v{golden['version']}: {len(queries)} queries, k={k}, "
        f"{REPETITIONS} runs per query, recall_k={settings.RETRIEVAL_RECALL_K}, "
        f"rrf_k={settings.RRF_K}, reranker={reranker.model_name}",
        f"Query embedding (excluded from the table): median "
        f"{statistics.median(embed_ms):.1f} ms, max {max(embed_ms):.1f} ms\n",
        "| Config | Search | Rerank | Mean P@5 | Mean R@5 | Median ms | Max ms |",
        "|---|---|---|---|---|---|---|",
        *summary,
        "\nRelevant budgets in bold.",
    ]
    return "\n".join(header + lines)


def main() -> int:
    golden = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    print(asyncio.run(run(golden)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
