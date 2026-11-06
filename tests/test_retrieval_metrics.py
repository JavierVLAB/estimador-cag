import json
from pathlib import Path

import pytest

from scripts.measure_retrieval import GOLDEN_SET_PATH, precision_at_k, recall_at_k


def test_precision_counts_every_relevant_chunk_in_the_top_k() -> None:
    retrieved = ["B1", "B1", "B2", "B3", "B1", "B9"]

    assert precision_at_k(retrieved, {"B1"}, 5) == pytest.approx(3 / 5)


def test_precision_divides_by_k_even_with_fewer_results() -> None:
    assert precision_at_k(["B1", "B1"], {"B1"}, 5) == pytest.approx(2 / 5)


def test_recall_counts_distinct_relevant_budgets() -> None:
    retrieved = ["B1", "B1", "B2", "B7", "B8"]

    assert recall_at_k(retrieved, {"B1", "B2", "B3", "B4"}, 5) == pytest.approx(2 / 4)


def test_golden_set_has_five_annotated_queries_over_known_budgets() -> None:
    golden = json.loads(Path(GOLDEN_SET_PATH).read_text(encoding="utf-8"))
    corpus = json.loads(Path("data/budgets_sample.json").read_text(encoding="utf-8"))
    budget_ids = {budget["budget_id"] for budget in corpus}

    assert golden["k"] == 5
    assert len(golden["queries"]) == 5
    for entry in golden["queries"]:
        assert entry["query"]
        assert set(entry["relevant_budget_ids"]) <= budget_ids
