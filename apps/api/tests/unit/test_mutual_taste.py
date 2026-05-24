"""Unit tests for the mutual-taste scoring service (T164).

Covers :func:`auxd_api.modules.seeding.mutual_taste.score_candidates` —
the pure-Python 4-factor (+ recency) per-candidate scoring routine
extracted from the T104 suggestions worker.

The tests build inputs in memory and assert on the typed
:class:`MutualTasteScore` output; no DB / mongomock involvement here.
Worker integration is exercised by :mod:`tests.unit.test_suggestions_algorithm`
which continues to pass against the worker's wrapper.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from auxd_api.modules.seeding.mutual_taste import (
    WEIGHT_FOLLOWED_BY_FOLLOWED,
    WEIGHT_LABEL_GENRE,
    WEIGHT_MUTUAL_TASTE,
    WEIGHT_RECENCY,
    WEIGHT_SHARED_SEED,
    MutualTasteScore,
    score_candidates,
)

_NOW = datetime(2026, 5, 23, tzinfo=UTC)


@pytest.mark.asyncio
async def test_mutual_taste_jaccard_overlap() -> None:
    """Viewer + candidate share half of their genre tags → overlap=2/3 (Jaccard)."""
    viewer = {"jazz": 1.0, "fusion": 0.6}
    candidate = {"jazz": 1.0, "fusion": 0.8, "ambient": 0.3}

    result = await score_candidates(
        viewer_id="user-viewer",
        viewer_genre_signature=viewer,
        candidate_user_ids=["cand-a"],
        candidate_genre_signatures={"cand-a": candidate},
        candidate_latest_activity={"cand-a": None},
        follows=[],
        follow_back_map={},
        critic_seed_user_ids=set(),
        viewer_followed_seed_ids=set(),
        candidate_followed_seed_ids={},
        followee_total=0,
        now=_NOW,
    )
    assert len(result) == 1
    score = result[0]
    # Jaccard: 2 shared / 3 union = 2/3.
    assert score.mutual_taste == pytest.approx(2 / 3)
    # No other signals fire.
    assert score.followed_by_followed == 0.0
    assert score.shared_seed == 0.0
    # Candidate's top genre is "jazz" — but the viewer's signature
    # doesn't expose it through the label_genre top-N path here either
    # (top-N is from viewer signature; "jazz" IS in viewer's top 3).
    assert score.label_genre == 1.0
    assert score.recency == 0.0
    expected_total = WEIGHT_MUTUAL_TASTE * (2 / 3) + WEIGHT_LABEL_GENRE * 1.0
    assert score.total == pytest.approx(expected_total)


@pytest.mark.asyncio
async def test_followed_by_followed_normalised_by_total() -> None:
    """Half of the viewer's followees also follow the candidate → 0.5 ratio."""
    result = await score_candidates(
        viewer_id="user-viewer",
        viewer_genre_signature={},
        candidate_user_ids=["cand-a"],
        candidate_genre_signatures={"cand-a": {}},
        candidate_latest_activity={"cand-a": None},
        follows=[],
        follow_back_map={"cand-a": {"followee-1", "followee-2"}},
        critic_seed_user_ids=set(),
        viewer_followed_seed_ids=set(),
        candidate_followed_seed_ids={},
        followee_total=4,
        now=_NOW,
    )
    score = result[0]
    assert score.followed_by_followed == pytest.approx(0.5)
    # No other signals → total is just the FBF weight × 0.5.
    assert score.total == pytest.approx(WEIGHT_FOLLOWED_BY_FOLLOWED * 0.5)


@pytest.mark.asyncio
async def test_shared_seed_boolean_via_intersection() -> None:
    """Viewer + candidate both follow a critic-seed → ``shared_seed = 1.0``."""
    result = await score_candidates(
        viewer_id="user-viewer",
        viewer_genre_signature={},
        candidate_user_ids=["cand-a", "cand-b"],
        candidate_genre_signatures={"cand-a": {}, "cand-b": {}},
        candidate_latest_activity={"cand-a": None, "cand-b": None},
        follows=[],
        follow_back_map={},
        critic_seed_user_ids={"seed-1", "seed-2"},
        viewer_followed_seed_ids={"seed-1"},
        candidate_followed_seed_ids={
            "cand-a": {"seed-1"},  # shares the seed → fires
            "cand-b": {"seed-2"},  # different seed → does not fire
        },
        followee_total=1,
        now=_NOW,
    )
    by_id = {s.user_id: s for s in result}
    assert by_id["cand-a"].shared_seed == 1.0
    assert by_id["cand-b"].shared_seed == 0.0
    assert by_id["cand-a"].total == pytest.approx(WEIGHT_SHARED_SEED)


@pytest.mark.asyncio
async def test_label_genre_top_n_match() -> None:
    """Candidate's top genre appears in viewer's top-3 → ``label_genre = 1.0``."""
    viewer = {"jazz": 1.0, "fusion": 0.8, "ambient": 0.6, "hip-hop": 0.5}
    candidate = {"ambient": 1.0, "drone": 0.4}
    result = await score_candidates(
        viewer_id="user-viewer",
        viewer_genre_signature=viewer,
        candidate_user_ids=["cand-a"],
        candidate_genre_signatures={"cand-a": candidate},
        candidate_latest_activity={"cand-a": None},
        follows=[],
        follow_back_map={},
        critic_seed_user_ids=set(),
        viewer_followed_seed_ids=set(),
        candidate_followed_seed_ids={},
        followee_total=0,
        now=_NOW,
    )
    assert result[0].label_genre == 1.0


@pytest.mark.asyncio
async def test_label_genre_top_n_miss() -> None:
    """Candidate's top genre is OUTSIDE viewer's top 3 → ``label_genre = 0.0``."""
    viewer = {"jazz": 1.0, "fusion": 0.8, "ambient": 0.6, "hip-hop": 0.5}
    candidate = {"hip-hop": 1.0, "drill": 0.4}
    result = await score_candidates(
        viewer_id="user-viewer",
        viewer_genre_signature=viewer,
        candidate_user_ids=["cand-a"],
        candidate_genre_signatures={"cand-a": candidate},
        candidate_latest_activity={"cand-a": None},
        follows=[],
        follow_back_map={},
        critic_seed_user_ids=set(),
        viewer_followed_seed_ids=set(),
        candidate_followed_seed_ids={},
        followee_total=0,
        now=_NOW,
    )
    # Viewer's top 3 by weight: jazz / fusion / ambient. hip-hop is #4.
    assert result[0].label_genre == 0.0


@pytest.mark.asyncio
async def test_recency_linear_decay() -> None:
    """14d → 1.0; 90d+ → 0.0; in between decays linearly."""
    candidates = {
        "fresh": _NOW - timedelta(days=5),  # well within 14d
        "edge": _NOW - timedelta(days=14),  # exactly at fresh cutoff
        "mid": _NOW - timedelta(days=52),  # halfway through the decay
        "stale": _NOW - timedelta(days=120),  # past the cliff
        "none": None,
    }
    result = await score_candidates(
        viewer_id="user-viewer",
        viewer_genre_signature={},
        candidate_user_ids=list(candidates.keys()),
        candidate_genre_signatures={cid: {} for cid in candidates},
        candidate_latest_activity=candidates,
        follows=[],
        follow_back_map={},
        critic_seed_user_ids=set(),
        viewer_followed_seed_ids=set(),
        candidate_followed_seed_ids={},
        followee_total=0,
        now=_NOW,
    )
    by_id = {s.user_id: s for s in result}
    assert by_id["fresh"].recency == 1.0
    assert by_id["edge"].recency == 1.0
    # mid = 52d total; (52 - 14) / (90 - 14) = 38/76 = 0.5 → recency = 0.5.
    assert by_id["mid"].recency == pytest.approx(0.5)
    assert by_id["stale"].recency == 0.0
    assert by_id["none"].recency == 0.0


@pytest.mark.asyncio
async def test_total_weight_sum_for_full_mix() -> None:
    """All five signals at max → total close to 1.0 with the canonical weighting."""
    viewer = {"jazz": 1.0, "fusion": 0.6}
    candidate = {"jazz": 1.0, "fusion": 0.8}  # full Jaccard = 1.0
    result = await score_candidates(
        viewer_id="user-viewer",
        viewer_genre_signature=viewer,
        candidate_user_ids=["cand-a"],
        candidate_genre_signatures={"cand-a": candidate},
        candidate_latest_activity={"cand-a": _NOW - timedelta(days=1)},
        follows=[],
        follow_back_map={"cand-a": {"f1", "f2", "f3", "f4"}},
        critic_seed_user_ids={"seed-1"},
        viewer_followed_seed_ids={"seed-1"},
        candidate_followed_seed_ids={"cand-a": {"seed-1"}},
        followee_total=4,
        now=_NOW,
    )
    score = result[0]
    expected = (
        WEIGHT_MUTUAL_TASTE * 1.0
        + WEIGHT_FOLLOWED_BY_FOLLOWED * 1.0
        + WEIGHT_SHARED_SEED * 1.0
        + WEIGHT_LABEL_GENRE * 1.0
        + WEIGHT_RECENCY * 1.0
    )
    assert score.total == pytest.approx(expected)
    # Sanity: weights sum to 1.0 exactly.
    weight_sum = (
        WEIGHT_MUTUAL_TASTE
        + WEIGHT_FOLLOWED_BY_FOLLOWED
        + WEIGHT_SHARED_SEED
        + WEIGHT_LABEL_GENRE
        + WEIGHT_RECENCY
    )
    assert pytest.approx(1.0) == weight_sum


def test_mutual_taste_score_is_frozen() -> None:
    """Frozen dataclass — guards against accidental mutation in callers."""
    s = MutualTasteScore(
        user_id="x",
        total=0.5,
        mutual_taste=0.5,
        followed_by_followed=0.0,
        shared_seed=0.0,
        label_genre=0.0,
        recency=0.0,
    )
    with pytest.raises(Exception):  # noqa: B017 - frozen-dataclass error
        s.total = 0.9  # type: ignore[misc]
