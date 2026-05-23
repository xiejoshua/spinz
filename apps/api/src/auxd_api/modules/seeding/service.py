"""Critic-seed scoring service (T117).

The seeding service is the engine behind two onboarding-adjacent
surfaces:

* :func:`get_card_recommendations_for_user` — batch precompute that the
  suggestions worker (:mod:`auxd_api.workers.suggestions_job`) calls once
  per cadence per user. Output feeds the Discover tab via the existing
  `Suggestion` collection.

* :func:`score_critics_by_genre_signature` — pure function used by both
  the batched precompute (T117) and the synchronous onboarding-time
  ordering (T117a in :mod:`auxd_api.modules.seeding.onboarding_service`).
  Lives here so the two surfaces share the same algorithm and stay
  consistent.

Scoring model (CR-001 + plan §12.2):

* Higher ``CriticSeed.priority`` is favoured (founder editorial).
* When the viewer has a non-empty genre signature, each critic gets a
  bonus proportional to the overlap (Jaccard) between their
  ``genre_signature`` and the viewer's.
* When the viewer has no signal yet (fresh signup, zero diary entries),
  the scoring degrades cleanly to priority-only — the AC for UJ-2
  (≥3 critics in the top 6 of the onboarding deck) is trivially
  satisfied because every candidate IS a critic.

The genre-signature computation itself is the responsibility of T163
(in §16 Seeding backend). Until T163 ships, viewers always present an
empty signature here and the service runs in priority-only mode.

Active filter: only ``CriticSeed.active == True`` candidates are
returned. Deactivated critics never appear in either surface.
"""

from __future__ import annotations

from dataclasses import dataclass

from auxd_api.modules.seeding.models import CriticSeed

# Genre-overlap bonus scale. Tuned conservatively so a single shared
# genre never outranks a priority gap of 20+; founder editorial intent
# dominates the ordering until per-user signal is rich.
_GENRE_BONUS_MAX = 20.0

# How many critic cards to surface in the default ranked list. Both
# T117 (Discover) and T117a (onboarding) consume from the top of this
# list; the latter slices it further to 6.
DEFAULT_CARD_LIMIT = 20


@dataclass(frozen=True, slots=True)
class ScoredCritic:
    """One ranked critic-seed candidate with the math-trail intact.

    ``score_components`` is purely transparency: the onboarding cards
    don't surface it (priority + bio is enough), but the Discover
    surface can use it for "why am I seeing this?" hints later.
    """

    seed: CriticSeed
    score: float
    score_components: dict[str, float]


def _genre_overlap(viewer_signature: list[str], critic_signature: list[str]) -> float:
    """Jaccard overlap of two tag sets, clamped to [0.0, 1.0].

    Empty viewer signature returns 0.0 (no signal → no genre bonus).
    Empty critic signature also returns 0.0 (legacy seeds without tags
    receive no bonus but stay competitive on priority alone).
    """
    if not viewer_signature or not critic_signature:
        return 0.0
    viewer_set = {tag.lower() for tag in viewer_signature if tag}
    critic_set = {tag.lower() for tag in critic_signature if tag}
    if not viewer_set or not critic_set:
        return 0.0
    intersection = viewer_set & critic_set
    union = viewer_set | critic_set
    return len(intersection) / len(union)


def score_critics_by_genre_signature(
    *,
    critics: list[CriticSeed],
    viewer_genre_signature: list[str],
) -> list[ScoredCritic]:
    """Score ``critics`` against ``viewer_genre_signature``; return ranked list.

    The output is sorted by ``score DESC`` with ``priority DESC`` as the
    tiebreaker so equal-score critics still respect the founder ranking.
    Inactive critics are filtered out before scoring (defence in depth —
    the read query should already restrict to ``active=True``).
    """
    scored: list[ScoredCritic] = []
    for seed in critics:
        if not seed.active:
            continue
        priority_score = float(seed.priority)
        overlap = _genre_overlap(viewer_genre_signature, seed.genre_signature)
        genre_bonus = overlap * _GENRE_BONUS_MAX
        total = priority_score + genre_bonus
        scored.append(
            ScoredCritic(
                seed=seed,
                score=total,
                score_components={
                    "priority": priority_score,
                    "genre_overlap": overlap,
                    "genre_bonus": genre_bonus,
                },
            )
        )
    scored.sort(key=lambda c: (-c.score, -c.seed.priority))
    return scored


async def get_card_recommendations_for_user(
    user_id: str,
    *,
    viewer_genre_signature: list[str] | None = None,
    limit: int = DEFAULT_CARD_LIMIT,
) -> list[ScoredCritic]:
    """Return the precomputed critic-seed deck for ``user_id``.

    Used by the suggestions worker (T104) to cache "who to follow"
    candidates per user. The frontend reads via the existing
    ``GET /api/v1/users/me/suggestions`` endpoint (the worker writes
    into the ``Suggestion`` collection — this service only computes
    the ranked list).

    ``viewer_genre_signature`` is ``None`` until T163 ships the per-user
    genre signature; the worker passes ``None`` for now and gets
    priority-only ordering, which is the documented fallback.
    """
    critics = await CriticSeed.find({"active": True}).to_list()
    scored = score_critics_by_genre_signature(
        critics=critics,
        viewer_genre_signature=viewer_genre_signature or [],
    )
    # The user_id parameter is reserved for future "exclude already-
    # followed critics" logic. The suggestions worker already applies
    # that filter at write time, so we don't duplicate here yet.
    _ = user_id
    return scored[:limit]


async def critic_seed_user_ids(user_ids: list[str]) -> set[str]:
    """Return the subset of ``user_ids`` that are an active critic seed (T152).

    Sidecar serializers (review feeds, profile cards, notifications)
    call this once per batch with the full set of user ids on the page,
    then look up ``user_id in result`` per card. The single query against
    the partial-active index makes the N+1 cost a non-issue even on
    100-card pages.
    """
    if not user_ids:
        return set()
    rows = await CriticSeed.find({"user_id": {"$in": user_ids}, "active": True}).to_list()
    return {row.user_id for row in rows}


__all__ = [
    "DEFAULT_CARD_LIMIT",
    "ScoredCritic",
    "critic_seed_user_ids",
    "get_card_recommendations_for_user",
    "score_critics_by_genre_signature",
]
