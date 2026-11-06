import pytest

from app.retrieval.fusion import reciprocal_rank_fusion


def test_consensus_beats_the_champion_of_a_single_list() -> None:
    # Lesson 03 example: S is 4th semantic and 2nd lexical, A is 1st semantic only,
    # B is 5th semantic and 4th lexical.
    semantic = ["A", "x1", "x2", "S", "B"]
    lexical = ["y1", "S", "y2", "B"]

    fused = [item for item, _ in reciprocal_rank_fusion([semantic, lexical], k=60)]

    assert fused[:3] == ["S", "B", "A"]


def test_scores_follow_the_rrf_formula() -> None:
    fused = dict(reciprocal_rank_fusion([["a", "b"], ["b"]], k=60))

    assert fused["a"] == pytest.approx(1 / 61)
    assert fused["b"] == pytest.approx(1 / 62 + 1 / 61)


def test_items_are_unique_and_k_changes_the_scores() -> None:
    fused_60 = reciprocal_rank_fusion([["a", "b"], ["b", "a"]], k=60)
    fused_0 = reciprocal_rank_fusion([["a", "b"], ["b", "a"]], k=0)

    assert sorted(item for item, _ in fused_60) == ["a", "b"]
    assert dict(fused_0)["a"] == pytest.approx(1 / 1 + 1 / 2)


def test_ties_keep_first_seen_order() -> None:
    fused = [item for item, _ in reciprocal_rank_fusion([["a"], ["b"]])]

    assert fused == ["a", "b"]


def test_negative_k_is_rejected() -> None:
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([["a"]], k=-1)
