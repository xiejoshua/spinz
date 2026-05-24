"""Mutual-taste candidate scoring service (T164).

Extracts the 4-factor (+ recency) per-candidate scoring previously
inlined in :mod:`auxd_api.workers.suggestions_job`. The worker now
fans out the database reads once, builds the inputs, and delegates the
per-candidate score computation to :func:`score_candidates` here.

Why split it out:

* The same algorithm is needed by future surfaces (e.g., Discover
  refresh, ad-hoc "people you should know" widgets) without requiring
  the worker's full materialisation pass.
* The unit-test surface for the algorithm becomes pure-Python: callers
  build inputs in the test, the scoring routine returns the typed
  output. No mongomock fixtures, no DB round-trip.

The five signals + weights mirror seeding-strategy.md §4 (and are
re-exported from :mod:`auxd_api.workers.suggestions_job` for backwards
compatibility):

* ``mutual_taste`` (40%) — Jaccard of viewer + candidate's diary genre
  signatures.
* ``followed_by_followed`` (30%) — fraction of viewer's followees who
  also follow the candidate.
* ``shared_seed`` (15%) — boolean: viewer + candidate both follow ≥1
  active critic-seed.
* ``label_genre`` (10%) — boolean: candidate's top genre appears in
  viewer's top-3 genres.
* ``recency`` (5%) — linear decay from 1.0 (within last 14d) to 0.0
  (>= 90d ago); diary entries older than 90d contribute nothing.

The total score is in ``[0, 1]`` and the call returns one
:class:`MutualTasteScore` per candidate, including the component
breakdown so callers can surface "why" tooltips.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from auxd_api.modules.social.models import Follow

# Weight constants — match seeding-strategy.md §4 and the legacy worker
# values. Re-exported from :mod:`auxd_api.workers.suggestions_job` so
# external imports keep working.
WEIGHT_MUTUAL_TASTE: Final[float] = 0.40
WEIGHT_FOLLOWED_BY_FOLLOWED: Final[float] = 0.30
WEIGHT_SHARED_SEED: Final[float] = 0.15
WEIGHT_LABEL_GENRE: Final[float] = 0.10
WEIGHT_RECENCY: Final[float] = 0.05

# Recency window: linear decay from "fresh" (=14d) to "stale" (>=90d).
_RECENCY_FRESH_DAYS: Final[int] = 14
_RECENCY_STALE_DAYS: Final[int] = 90

# Number of viewer top-genres considered for the label/genre overlap
# boolean.
_LABEL_GENRE_TOP_N: Final[int] = 3


@dataclass(frozen=True, slots=True)
class MutualTasteScore:
    """Per-candidate score breakdown for the 4-factor + recency formula.

    ``total`` is the weighted sum in ``[0, 1]``; the per-component
    fields are the *normalised* signal values (each in ``[0, 1]``),
    NOT the weighted contributions. To recover the contribution from
    e.g. ``mutual_taste``, multiply by :data:`WEIGHT_MUTUAL_TASTE`.
    """

    user_id: str
    total: float
    mutual_taste: float
    followed_by_followed: float
    shared_seed: float
    label_genre: float
    recency: float


def _genre_jaccard(
    viewer: Mapping[str, float],
    candidate: Mapping[str, float],
) -> float:
    """Jaccard overlap between two normalized genre signatures.

    Both signatures are weight maps from
    :func:`auxd_api.modules.seeding.genre_signature.compute_genre_signature`
    — the keys are the genre tags. We use set-based Jaccard rather than
    a weighted dot product because the weight maps are sparse + already
    normalised to peak=1.0; the simple form is a robust first cut and
    matches the existing critic-seed scoring's interpretation of
    "overlap".
    """
    if not viewer or not candidate:
        return 0.0
    viewer_set = {k.lower() for k in viewer}
    candidate_set = {k.lower() for k in candidate}
    if not viewer_set or not candidate_set:
        return 0.0
    intersection = viewer_set & candidate_set
    union = viewer_set | candidate_set
    return len(intersection) / len(union)


def _viewer_top_genres(signature: Mapping[str, float]) -> set[str]:
    """Return the top-N genres (by weight) from the viewer's signature."""
    if not signature:
        return set()
    sorted_items = sorted(signature.items(), key=lambda pair: (-pair[1], pair[0]))
    return {key for key, _ in sorted_items[:_LABEL_GENRE_TOP_N]}


def _candidate_top_genre(signature: Mapping[str, float]) -> str | None:
    """Return the single highest-weight genre for the candidate, if any."""
    if not signature:
        return None
    return max(signature.items(), key=lambda pair: (pair[1], pair[0]))[0]


def _recency_score(latest_activity: datetime | None, *, now: datetime) -> float:
    """Linear decay from 1.0 (within 14d) to 0.0 (>=90d).

    ``None`` (no activity recorded) returns 0.0. Future timestamps are
    treated as "now" (defensive — should not happen with normal data).
    """
    if latest_activity is None:
        return 0.0
    # Normalise tz: mongomock-motor strips tzinfo on read.
    if latest_activity.tzinfo is None:
        latest_activity = latest_activity.replace(tzinfo=UTC)
    age = now - latest_activity
    if age <= timedelta(days=_RECENCY_FRESH_DAYS):
        return 1.0
    if age >= timedelta(days=_RECENCY_STALE_DAYS):
        return 0.0
    decay_span = _RECENCY_STALE_DAYS - _RECENCY_FRESH_DAYS
    decay_age = age.total_seconds() / 86400.0 - _RECENCY_FRESH_DAYS
    return max(0.0, 1.0 - (decay_age / decay_span))


async def score_candidates(
    *,
    viewer_id: str,
    viewer_genre_signature: Mapping[str, float],
    candidate_user_ids: list[str],
    candidate_genre_signatures: Mapping[str, Mapping[str, float]],
    candidate_latest_activity: Mapping[str, datetime | None],
    follows: list[Follow],  # unused at MVP; reserved for future heuristics
    follow_back_map: Mapping[str, set[str]],
    critic_seed_user_ids: set[str],
    viewer_followed_seed_ids: set[str],
    candidate_followed_seed_ids: Mapping[str, set[str]],
    followee_total: int,
    now: datetime | None = None,
) -> list[MutualTasteScore]:
    """Score each candidate against the viewer's pre-built inputs.

    The caller is responsible for materialising the inputs once per
    viewer (the suggestions worker does this) so the scoring routine
    stays pure + testable.

    ``follow_back_map`` maps ``candidate_id → set(viewer_followees who
    follow this candidate)``; the followed-by-followed signal divides
    its size by ``followee_total`` to produce a ratio in ``[0, 1]``.
    """
    _ = follows  # reserved — future heuristics may inspect raw rows
    _ = viewer_id  # the scoring is symmetric; reserved for telemetry
    _ = critic_seed_user_ids  # caller-side validation already filtered

    when = now if now is not None else datetime.now(UTC)
    viewer_top_genres = _viewer_top_genres(viewer_genre_signature)

    scores: list[MutualTasteScore] = []
    for cid in candidate_user_ids:
        candidate_sig = candidate_genre_signatures.get(cid, {})
        mt_overlap = _genre_jaccard(viewer_genre_signature, candidate_sig)

        followers_in_common = follow_back_map.get(cid, set())
        if followee_total > 0 and followers_in_common:
            fbf_ratio = min(1.0, len(followers_in_common) / followee_total)
        else:
            fbf_ratio = 0.0

        candidate_seeds = candidate_followed_seed_ids.get(cid, set())
        shared_seed = 1.0 if (viewer_followed_seed_ids & candidate_seeds) else 0.0

        cand_top_genre = _candidate_top_genre(candidate_sig)
        label_genre = (
            1.0
            if (cand_top_genre is not None and cand_top_genre.lower() in viewer_top_genres)
            else 0.0
        )

        recency = _recency_score(candidate_latest_activity.get(cid), now=when)

        total = (
            WEIGHT_MUTUAL_TASTE * mt_overlap
            + WEIGHT_FOLLOWED_BY_FOLLOWED * fbf_ratio
            + WEIGHT_SHARED_SEED * shared_seed
            + WEIGHT_LABEL_GENRE * label_genre
            + WEIGHT_RECENCY * recency
        )
        # Clamp defensively — weights sum to 1.0 so a happy-path
        # signal-saturated candidate sits at 1.0, but a future tuning
        # pass could shift weights and this stops a buggy edit from
        # breaking the [0,1] contract.
        total = max(0.0, min(1.0, total))

        scores.append(
            MutualTasteScore(
                user_id=cid,
                total=total,
                mutual_taste=mt_overlap,
                followed_by_followed=fbf_ratio,
                shared_seed=shared_seed,
                label_genre=label_genre,
                recency=recency,
            )
        )
    return scores


__all__ = [
    "WEIGHT_FOLLOWED_BY_FOLLOWED",
    "WEIGHT_LABEL_GENRE",
    "WEIGHT_MUTUAL_TASTE",
    "WEIGHT_RECENCY",
    "WEIGHT_SHARED_SEED",
    "MutualTasteScore",
    "score_candidates",
]
