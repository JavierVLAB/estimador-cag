"""Reciprocal Rank Fusion: merge rankings using positions only, never raw scores.

Cosine distances and ts_rank values live on scales that cannot be added, so each
ranking contributes 1 / (k + rank) per item and the contributions are summed.
Items that rank reasonably well in several lists beat the champion of a single one.
"""

from collections import defaultdict
from collections.abc import Hashable, Sequence

# Smoothing constant from the original RRF paper; larger values flatten the
# advantage of the top positions.
DEFAULT_RRF_K = 60


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[Hashable]], k: int = DEFAULT_RRF_K
) -> list[tuple[Hashable, float]]:
    """Fuse ranked lists of ids into one list of (id, score), best first.

    Ranks start at 1. Ties keep the order in which ids were first seen, so the
    result is deterministic.
    """
    if k < 0:
        raise ValueError("RRF smoothing constant k must be non-negative")
    scores: dict[Hashable, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)
