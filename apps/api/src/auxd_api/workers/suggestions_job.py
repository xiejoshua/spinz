"""Suggested-follow precompute worker (T104).

This module owns the heuristic that produces "people you might want to
follow" suggestions. Per ``seeding-strategy.md`` §4 the score is a
weighted sum of five signals:

* **mutual-taste (40%)** — overlap between the viewer's high-rating
  (``rating ∈ {4, 4.5, 5}``) album set and the candidate's.
* **followed-by-followed (30%)** — how many of the viewer's followees
  also follow the candidate (the "your friends follow X" social proof).
* **shared-seed (15%)** — the viewer + candidate both follow ≥1 of the
  same critic-seed accounts (taste cohort).
* **label / genre (10%)** — shared label or genre signal across each
  user's top-5 albums by rating.
* **recency (5%)** — candidate has any diary entry in the last 30 days
  (boosts active users).

Each signal is normalised to ``[0, 1]`` and contributes its weight to
the final score. The score itself stays in ``[0, 1]`` so the API surface
can sort + threshold without surprises.

Exclusion rules (applied BEFORE scoring, to keep work cheap):

* The viewer themselves is never a candidate.
* Anyone the viewer already follows (``state=ACCEPTED``) is excluded.
* Anyone the viewer has blocked, OR who has blocked the viewer, is
  excluded (the visibility matrix demands symmetric hiding).
* Anyone the viewer has dismissed in the last 30 days is excluded (the
  TTL on :class:`SuggestionDismissal.dismissed_at` keeps the row alive
  for that window, then expires it).

The worker is an async function rather than a class so the scheduling
glue (arq cron entry) can be added independently. Today it is invoked
from tests and (eventually) from the cron registry in
``apps/api/src/auxd_api/workers/main.py`` — see the TODO at module
bottom.

Algorithm notes:

* The "top-5 albums by rating" lookup keys on rating-DESC and
  logged-at-DESC so two equally-rated albums break ties by recency.
* Label / genre overlap is a flat boolean (≥1 shared tag) at MVP — the
  ML-ish version would compute Jaccard. The boolean approach keeps the
  worker O(N) in the candidate count and is good enough for the
  10%-weight slot in the formula.
* The candidate pool is bounded by reading every user but capping the
  worker output at ``MAX_SUGGESTIONS_PER_USER`` rows per user. The arq
  cadence (every N hours) means we don't need to be clever about
  pagination — even a 100k-user instance is a one-time-per-cadence
  query.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from typing import Final

from pymongo.errors import DuplicateKeyError

from auxd_api.modules.albums.models import Album
from auxd_api.modules.diary.models import DiaryEntry
from auxd_api.modules.seeding.models import CriticSeed
from auxd_api.modules.social.models import Block, Follow, FollowState
from auxd_api.modules.social.suggestions_models import (
    Suggestion,
    SuggestionDismissal,
)
from auxd_api.modules.users.models import User

_LOGGER = logging.getLogger("auxd.suggestions_job")

# Algorithm weight constants — defined here so the test suite can import
# and assert on them, and so a future tuning pass leaves one source of
# truth.
WEIGHT_MUTUAL_TASTE: Final[float] = 0.40
WEIGHT_FOLLOWED_BY_FOLLOWED: Final[float] = 0.30
WEIGHT_SHARED_SEED: Final[float] = 0.15
WEIGHT_LABEL_GENRE: Final[float] = 0.10
WEIGHT_RECENCY: Final[float] = 0.05

# "High rating" threshold — only ratings in this set contribute to the
# mutual-taste set. Mirrors the seeding-strategy.md §4 definition.
HIGH_RATINGS: Final[frozenset[float]] = frozenset({4.0, 4.5, 5.0})

# Hard cap on output rows per user. The API surface paginates with a
# small ``limit`` (default 5, max 20) so anything past 50 is wasted work
# at the worker level.
MAX_SUGGESTIONS_PER_USER: Final[int] = 50

# Recency window for the 5% boost — "candidate has logged anything in
# the last RECENT_LOG_WINDOW_DAYS days".
RECENT_LOG_WINDOW_DAYS: Final[int] = 30

# Top-N albums used as the label/genre source for the candidate side of
# the 10% signal.
TOP_ALBUM_LIMIT: Final[int] = 5


__all__ = [
    "HIGH_RATINGS",
    "MAX_SUGGESTIONS_PER_USER",
    "RECENT_LOG_WINDOW_DAYS",
    "TOP_ALBUM_LIMIT",
    "WEIGHT_FOLLOWED_BY_FOLLOWED",
    "WEIGHT_LABEL_GENRE",
    "WEIGHT_MUTUAL_TASTE",
    "WEIGHT_RECENCY",
    "WEIGHT_SHARED_SEED",
    "ScoredCandidate",
    "compute_suggestions_for_user",
    "score_candidate",
]


# ---------------------------------------------------------------------------
# Pure scoring (testable without DB)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    """Return shape from :func:`score_candidate` — the pure inner scorer.

    ``score`` is in ``[0, 1]``. ``reasons`` lists every signal that
    contributed a non-zero component, in the order they appear in the
    formula (mutual-taste → followed-by-followed → shared-seed →
    label/genre → recency). The reasons are wire-stable strings.
    """

    score: float
    reasons: list[str]


def score_candidate(
    *,
    mutual_taste_overlap: float,
    followed_by_followed_count: int,
    followed_by_followed_total: int,
    shared_seed: bool,
    label_genre_overlap: bool,
    recent_activity: bool,
) -> ScoredCandidate:
    """Compute the score + reason tags for one candidate.

    Each input is the *already-normalised* signal value, so this function
    is pure arithmetic + tag assembly. Splitting it from the database
    fan-out makes unit tests trivial (no fixtures, no Mongo).

    ``mutual_taste_overlap`` is the Jaccard-style overlap fraction in
    ``[0, 1]`` between the viewer's and candidate's high-rating sets.
    ``followed_by_followed_count`` / ``..._total`` are normalised in-line
    so the caller doesn't pre-divide; if ``_total`` is zero the
    contribution is zero. The boolean flags either contribute their full
    weight or zero.
    """
    components: list[str] = []
    score = 0.0

    if mutual_taste_overlap > 0.0:
        # Clamp defensively — mutual_taste_overlap should already be in
        # [0,1] but a future tweak that miscomputes could otherwise blow
        # the [0,1] score contract.
        contrib = WEIGHT_MUTUAL_TASTE * min(1.0, max(0.0, mutual_taste_overlap))
        score += contrib
        components.append("mutual_taste")

    if followed_by_followed_count > 0 and followed_by_followed_total > 0:
        ratio = followed_by_followed_count / followed_by_followed_total
        contrib = WEIGHT_FOLLOWED_BY_FOLLOWED * min(1.0, max(0.0, ratio))
        score += contrib
        components.append("followed_by_followed")

    if shared_seed:
        score += WEIGHT_SHARED_SEED
        components.append("shared_seed")

    if label_genre_overlap:
        score += WEIGHT_LABEL_GENRE
        components.append("label_genre")

    if recent_activity:
        score += WEIGHT_RECENCY
        components.append("recency")

    # Clamp the final score so a future bug can't surface > 1.0 via the
    # API. The arithmetic above shouldn't exceed 1.0 (weights sum to
    # 1.00) but the clamp is defence-in-depth.
    return ScoredCandidate(score=min(1.0, score), reasons=components)


# ---------------------------------------------------------------------------
# DB fan-out + persistence
# ---------------------------------------------------------------------------


def _high_rating_album_ids(entries: list[DiaryEntry]) -> set[str]:
    """Return the set of album ids in the user's "high rating" cluster."""
    return {
        entry.album_id
        for entry in entries
        if entry.rating is not None and entry.rating in HIGH_RATINGS
    }


def _top_n_album_ids(entries: list[DiaryEntry], n: int) -> list[str]:
    """Return up to ``n`` album ids ordered by rating DESC then logged_at DESC.

    Entries with no rating sort last; ties on rating break by
    ``logged_at`` (more recent first). Used as the "top-5 albums" source
    for the label/genre overlap signal.
    """
    ranked = sorted(
        entries,
        key=lambda entry: (
            -(entry.rating if entry.rating is not None else -1.0),
            -entry.logged_at.timestamp(),
        ),
    )
    seen: list[str] = []
    seen_set: set[str] = set()
    for entry in ranked:
        if entry.album_id in seen_set:
            continue
        seen.append(entry.album_id)
        seen_set.add(entry.album_id)
        if len(seen) >= n:
            break
    return seen


def _label_genre_signature(albums: list[Album]) -> tuple[set[str], set[str]]:
    """Return ``(labels, genres)`` aggregated across ``albums``.

    Labels are normalised to lowercase strings; ``None`` labels are
    skipped. Genres are taken as-is from the album document because the
    free-text genre tags are already lowercase by convention.
    """
    labels: set[str] = set()
    genres: set[str] = set()
    for album in albums:
        if album.label:
            labels.add(album.label.casefold())
        for genre in album.genres:
            genres.add(genre.casefold())
    return labels, genres


async def _excluded_user_ids(viewer_id: str) -> set[str]:
    """Aggregate every user id the algorithm must skip.

    Skips:

    * the viewer themselves (no self-suggestion),
    * already-accepted followees,
    * blocked users (in either direction),
    * recently-dismissed candidates (TTL keeps the row for 30 days).
    """
    excluded: set[str] = {viewer_id}

    follows = await Follow.find(
        {"follower_id": viewer_id, "state": FollowState.ACCEPTED.value}
    ).to_list()
    excluded.update(row.followee_id for row in follows)

    blocks = await Block.find(
        {"$or": [{"blocker_id": viewer_id}, {"blockee_id": viewer_id}]}
    ).to_list()
    for block in blocks:
        if block.blocker_id == viewer_id:
            excluded.add(block.blockee_id)
        else:
            excluded.add(block.blocker_id)

    dismissals = await SuggestionDismissal.find({"user_id": viewer_id}).to_list()
    excluded.update(row.suggested_user_id for row in dismissals)

    return excluded


async def _candidate_pool(viewer_id: str, excluded: set[str]) -> list[User]:
    """Return every candidate user not in the exclusion set.

    At MVP every active user is a potential candidate. The exclusion set
    is materialised in Python so the Mongo ``$nin`` predicate stays
    bounded; for a 100k-user instance this is a few MB of ids — well
    within an in-memory query plan.
    """
    return await User.find({"_id": {"$nin": list(excluded)}}).to_list()


async def compute_suggestions_for_user(user_id: str) -> int:
    """Recompute the suggestion rows for ``user_id`` and persist them.

    Returns the number of rows written. Caller is responsible for the
    scheduling cadence; today this is invoked directly from tests, and
    will be registered with arq cron at T009 deploy worker config (see
    TODO at module bottom).

    Behaviour:

    1. Build the exclusion set (self / follows / blocks / dismissals).
    2. Read the viewer's diary entries + top-5 albums + critic-seed
       follows once, up-front, so the per-candidate work is just lookups
       into already-fetched structures.
    3. For each candidate, compute the five signals + final score, and
       upsert into the ``suggestions`` collection. Existing rows for
       this viewer are deleted before insert so the row set always
       matches the latest run (we don't carry over stale candidates that
       have since become ineligible).
    4. Return the number of rows persisted so the caller (or the cron
       wrapper) can log + alert on anomalies.
    """
    excluded = await _excluded_user_ids(user_id)
    candidates = await _candidate_pool(user_id, excluded)
    if not candidates:
        # Always clear stale rows even when no candidates remain — the
        # previous run might have written a row for someone who has
        # since been blocked / followed / dismissed.
        await Suggestion.find({"user_id": user_id}).delete()
        return 0

    viewer_entries = await DiaryEntry.find({"user_id": user_id, "deleted_at": None}).to_list()
    viewer_high_rating_albums = _high_rating_album_ids(viewer_entries)
    viewer_top_album_ids = _top_n_album_ids(viewer_entries, TOP_ALBUM_LIMIT)
    viewer_top_albums = (
        await Album.find({"_id": {"$in": viewer_top_album_ids}}).to_list()
        if viewer_top_album_ids
        else []
    )
    viewer_labels, viewer_genres = _label_genre_signature(viewer_top_albums)

    viewer_followees = await Follow.find(
        {"follower_id": user_id, "state": FollowState.ACCEPTED.value}
    ).to_list()
    viewer_followee_ids = {row.followee_id for row in viewer_followees}

    # The "your followees follow this candidate" signal — fetch every
    # follow originated by one of the viewer's followees, then count
    # incoming hits per candidate. One query covers the whole graph
    # walk.
    followee_outgoing: list[Follow] = []
    if viewer_followee_ids:
        followee_outgoing = await Follow.find(
            {
                "follower_id": {"$in": list(viewer_followee_ids)},
                "state": FollowState.ACCEPTED.value,
            }
        ).to_list()
    followed_by_followed_counter: Counter[str] = Counter(
        row.followee_id for row in followee_outgoing
    )
    followee_total = len(viewer_followee_ids)

    # Shared-seed signal: the set of critic-seed user_ids that the
    # viewer follows.
    active_seeds = await CriticSeed.find({"active": True}).to_list()
    active_seed_user_ids = {seed.user_id for seed in active_seeds}
    viewer_followed_seeds = viewer_followee_ids & active_seed_user_ids

    # Pre-fetch candidate diary entries + recent-activity bookkeeping in
    # one batch keyed by user_id, then partition in Python.
    candidate_ids = [user.id for user in candidates]
    candidate_entries = await DiaryEntry.find(
        {"user_id": {"$in": candidate_ids}, "deleted_at": None}
    ).to_list()
    entries_by_user: dict[str, list[DiaryEntry]] = {}
    for entry in candidate_entries:
        entries_by_user.setdefault(entry.user_id, []).append(entry)

    # Pre-fetch candidate follows so we can compute the shared-seed
    # signal for each candidate without per-candidate queries.
    candidate_outgoing_follows = await Follow.find(
        {
            "follower_id": {"$in": candidate_ids},
            "state": FollowState.ACCEPTED.value,
        }
    ).to_list()
    candidate_followees_by_user: dict[str, set[str]] = {}
    for row in candidate_outgoing_follows:
        candidate_followees_by_user.setdefault(row.follower_id, set()).add(row.followee_id)

    # Pre-fetch every top-5 album referenced by any candidate so the
    # label/genre comparison is in-memory.
    candidate_top_album_ids_by_user: dict[str, list[str]] = {}
    referenced_album_ids: set[str] = set()
    for candidate_id, entries in entries_by_user.items():
        top_ids = _top_n_album_ids(entries, TOP_ALBUM_LIMIT)
        candidate_top_album_ids_by_user[candidate_id] = top_ids
        referenced_album_ids.update(top_ids)
    referenced_albums = (
        await Album.find({"_id": {"$in": list(referenced_album_ids)}}).to_list()
        if referenced_album_ids
        else []
    )
    album_by_id = {album.id: album for album in referenced_albums}

    # Recent-activity cutoff — "candidate has any logged_at within the
    # last RECENT_LOG_WINDOW_DAYS days". Use the viewer's wall-clock
    # ``now`` so the test suite can monkeypatch ``datetime.now`` if it
    # needs to.
    from datetime import UTC, datetime, timedelta

    recency_cutoff = datetime.now(UTC) - timedelta(days=RECENT_LOG_WINDOW_DAYS)

    def _is_recent(value: datetime) -> bool:
        """Return True iff ``value`` >= ``recency_cutoff``.

        mongomock-motor strips tzinfo from BSON datetimes on read, so a
        direct ``>=`` between an aware cutoff and a naive value raises
        :class:`TypeError`. Coerce to UTC when naive before comparing —
        production Mongo also stores UTC, so this is semantically a no-op
        for real reads and a tz-fix for the in-memory test path.
        """
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value >= recency_cutoff

    scored: list[tuple[User, ScoredCandidate]] = []
    for candidate in candidates:
        # 1. Mutual-taste — Jaccard-ish: shared / union. Both empty → 0.
        candidate_entries_for_user = entries_by_user.get(candidate.id, [])
        candidate_high = _high_rating_album_ids(candidate_entries_for_user)
        if viewer_high_rating_albums and candidate_high:
            shared_high = len(viewer_high_rating_albums & candidate_high)
            union_high = len(viewer_high_rating_albums | candidate_high)
            mutual_taste_overlap = shared_high / union_high if union_high else 0.0
        else:
            mutual_taste_overlap = 0.0

        # 2. Followed-by-followed — how many of the viewer's followees
        # follow this candidate, normalised by total followees count.
        followed_by_followed_count = followed_by_followed_counter.get(candidate.id, 0)

        # 3. Shared-seed — viewer + candidate both follow ≥1 of the same
        # active critic-seed account.
        candidate_followees = candidate_followees_by_user.get(candidate.id, set())
        candidate_followed_seeds = candidate_followees & active_seed_user_ids
        shared_seed = bool(viewer_followed_seeds & candidate_followed_seeds)

        # 4. Label / genre — pull the candidate's top-5 album metadata
        # and check for a shared label OR genre.
        candidate_top_albums = [
            album_by_id[album_id]
            for album_id in candidate_top_album_ids_by_user.get(candidate.id, [])
            if album_id in album_by_id
        ]
        candidate_labels, candidate_genres = _label_genre_signature(candidate_top_albums)
        label_genre_overlap = bool(
            (viewer_labels & candidate_labels) or (viewer_genres & candidate_genres)
        )

        # 5. Recency — any diary entry in the last 30 days.
        recent_activity = any(_is_recent(entry.logged_at) for entry in candidate_entries_for_user)

        result = score_candidate(
            mutual_taste_overlap=mutual_taste_overlap,
            followed_by_followed_count=followed_by_followed_count,
            followed_by_followed_total=followee_total,
            shared_seed=shared_seed,
            label_genre_overlap=label_genre_overlap,
            recent_activity=recent_activity,
        )
        if result.score > 0.0:
            scored.append((candidate, result))

    # Sort highest-score first; ties break by candidate KSUID for
    # deterministic test output.
    scored.sort(key=lambda pair: (-pair[1].score, pair[0].id))
    scored = scored[:MAX_SUGGESTIONS_PER_USER]

    # Clear previous rows for this viewer so the persisted state always
    # mirrors the most recent computation. Doing this before insert
    # avoids the cross-run leftovers problem.
    await Suggestion.find({"user_id": user_id}).delete()

    written = 0
    for candidate, result in scored:
        row = Suggestion(
            user_id=user_id,
            suggested_user_id=candidate.id,
            score=result.score,
            reasons=list(result.reasons),
        )
        try:
            await row.insert()
        except DuplicateKeyError:
            # Defence in depth — the delete-all above means this should
            # not fire, but if a race wrote a row in the meantime we
            # update it instead of failing the whole worker run.
            existing = await Suggestion.find_one(
                {"user_id": user_id, "suggested_user_id": candidate.id}
            )
            if existing is not None:
                existing.score = result.score
                existing.reasons = list(result.reasons)
                from datetime import UTC as _UTC
                from datetime import datetime as _datetime

                existing.computed_at = _datetime.now(_UTC)
                await existing.save()
        written += 1

    _LOGGER.info(
        "worker.suggestions.computed",
        extra={
            "event": "worker.suggestions.computed",
            "user_id": user_id,
            "candidates": len(candidates),
            "written": written,
        },
    )
    return written


# TODO: register in arq cron at T009 deploy worker config
# Expected entry shape (mirrors the album-cache cron entries):
#
#     cron(
#         compute_suggestions_for_user,
#         hour={3, 9, 15, 21},  # every 6h
#         minute=0,
#         run_at_startup=False,
#     )
#
# The cron callable will need a wrapping job that iterates active users
# (User.status == ACTIVE) and dispatches per-user computation; today the
# function is single-user only so tests can drive it directly.
