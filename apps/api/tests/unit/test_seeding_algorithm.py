"""Unit tests for the critic-seed scoring algorithm (T117).

Covers the pure `score_critics_by_genre_signature` function only — the
DB-fanout `get_card_recommendations_for_user` is exercised via the
integration tests in test_onboarding_endpoint.py.
"""

from __future__ import annotations

from auxd_api.modules.seeding.models import CriticSeed
from auxd_api.modules.seeding.service import (
    _GENRE_BONUS_MAX,
    ScoredCritic,
    score_critics_by_genre_signature,
)


def _seed(
    user_id: str,
    *,
    priority: int = 50,
    active: bool = True,
    genres: list[str] | None = None,
) -> CriticSeed:
    return CriticSeed(
        id=f"seed-{user_id}",
        user_id=user_id,
        priority=priority,
        active=active,
        genre_signature=genres or [],
        public_bio=None,
    )


def test_priority_only_ordering_when_no_viewer_signature() -> None:
    """Fresh-signup viewers (no genre signature) get pure priority ordering."""
    critics = [
        _seed("user-a", priority=30),
        _seed("user-b", priority=80),
        _seed("user-c", priority=50),
    ]
    result = score_critics_by_genre_signature(
        critics=critics,
        viewer_genre_signature=[],
    )
    assert [c.seed.user_id for c in result] == ["user-b", "user-c", "user-a"]
    # Every score equals priority (no genre bonus path).
    assert all(c.score_components["genre_bonus"] == 0.0 for c in result)


def test_inactive_critics_excluded() -> None:
    critics = [
        _seed("user-a", priority=80, active=True),
        _seed("user-b", priority=90, active=False),  # deactivated — drop
        _seed("user-c", priority=70, active=True),
    ]
    result = score_critics_by_genre_signature(
        critics=critics,
        viewer_genre_signature=[],
    )
    assert [c.seed.user_id for c in result] == ["user-a", "user-c"]


def test_genre_overlap_boosts_score() -> None:
    """A perfect genre-match closes a 15-point priority gap.

    Bonus scale: _GENRE_BONUS_MAX = 20.0 (perfect overlap). A 1-point
    priority gap dressed up with full overlap is a trivial case; we
    pick a 15-point gap so this also documents that genre signal IS
    strong enough to outweigh "small" priority differences.
    """
    critics = [
        _seed("user-jazzhead", priority=50, genres=["jazz"]),  # 50 + 20 = 70
        _seed("user-poprock", priority=65, genres=["pop", "rock"]),  # 65 + 0 = 65
    ]
    result = score_critics_by_genre_signature(
        critics=critics,
        viewer_genre_signature=["jazz"],
    )
    assert [c.seed.user_id for c in result] == ["user-jazzhead", "user-poprock"]
    jazzhead = next(c for c in result if c.seed.user_id == "user-jazzhead")
    assert jazzhead.score_components["genre_overlap"] == 1.0
    assert jazzhead.score_components["genre_bonus"] == _GENRE_BONUS_MAX


def test_perfect_genre_match_caps_at_bonus_max() -> None:
    critics = [_seed("user-twin", priority=50, genres=["jazz", "fusion"])]
    result = score_critics_by_genre_signature(
        critics=critics,
        viewer_genre_signature=["jazz", "fusion"],
    )
    bonus = result[0].score_components["genre_bonus"]
    assert bonus == _GENRE_BONUS_MAX  # Jaccard = 1.0 → full bonus
    assert result[0].score == 50.0 + _GENRE_BONUS_MAX


def test_genre_overlap_is_case_insensitive() -> None:
    critics = [_seed("user-x", priority=50, genres=["Jazz", "FUSION"])]
    result = score_critics_by_genre_signature(
        critics=critics,
        viewer_genre_signature=["jazz", "fusion"],
    )
    assert result[0].score_components["genre_overlap"] == 1.0


def test_empty_critic_signature_yields_no_bonus() -> None:
    critics = [
        _seed("legacy-seed", priority=90, genres=[]),  # legacy row without tags
    ]
    result = score_critics_by_genre_signature(
        critics=critics,
        viewer_genre_signature=["jazz", "fusion"],
    )
    assert result[0].score == 90.0
    assert result[0].score_components["genre_bonus"] == 0.0


def test_tiebreak_uses_priority_descending() -> None:
    """Equal genre overlap → priority tiebreaks."""
    critics = [
        _seed("user-a", priority=70, genres=["jazz"]),
        _seed("user-b", priority=80, genres=["jazz"]),
    ]
    result = score_critics_by_genre_signature(
        critics=critics,
        viewer_genre_signature=["jazz"],
    )
    # Both get the same overlap (1.0), so the higher-priority one wins.
    assert [c.seed.user_id for c in result] == ["user-b", "user-a"]


def test_scored_critic_is_immutable_dataclass() -> None:
    """Frozen-dataclass guard — accidental mutation would corrupt caches."""
    sc = ScoredCritic(
        seed=_seed("user-x"),
        score=42.0,
        score_components={"priority": 42.0},
    )
    try:
        sc.score = 99.0  # type: ignore[misc]
    except Exception as exc:  # noqa: BLE001
        assert "frozen" in str(exc).lower() or "FrozenInstance" in type(exc).__name__
    else:
        raise AssertionError("ScoredCritic should be frozen")
