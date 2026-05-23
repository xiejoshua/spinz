"""Unit tests for the suggestion scoring algorithm (T104).

Two layers under test:

* :func:`score_candidate` — pure arithmetic, no fixtures. Asserts each
  signal contributes its weight independently and that mixes compose
  cleanly.
* :func:`compute_suggestions_for_user` — exercised against the in-memory
  mongomock database via the autouse session fixture, with the actual
  exclusion rules (follow / block / dismissal) verified end-to-end.

The arq cron scheduling glue (cron entry registration) is out of scope
for this layer — the worker function is invoked directly here so the
tests focus on algorithm correctness.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio

from auxd_api.modules.albums.models import Album, AlbumSource
from auxd_api.modules.diary.models import DiaryEntry, Visibility
from auxd_api.modules.seeding.models import CriticSeed
from auxd_api.modules.social.models import Block, BlockReason, Follow, FollowState
from auxd_api.modules.social.suggestions_models import (
    Suggestion,
    SuggestionDismissal,
)
from auxd_api.modules.users.models import User
from auxd_api.workers.suggestions_job import (
    WEIGHT_FOLLOWED_BY_FOLLOWED,
    WEIGHT_LABEL_GENRE,
    WEIGHT_MUTUAL_TASTE,
    WEIGHT_RECENCY,
    WEIGHT_SHARED_SEED,
    compute_suggestions_for_user,
    score_candidate,
)


def _make_user(user_id: str, handle: str) -> User:
    return User(
        id=user_id,
        handle=handle,
        email=f"{handle}@example.com",
        password_hash="$argon2id$test-hash",
        display_name=handle.capitalize(),
    )


def _make_album(
    album_id: str,
    *,
    label: str | None = None,
    genres: list[str] | None = None,
) -> Album:
    return Album(
        id=album_id,
        mbid=None,
        title=f"Album {album_id}",
        artist_credit="Tester",
        source=AlbumSource.MUSICBRAINZ,
        cache_expires_at=datetime.now(UTC) + timedelta(days=7),
        label=label,
        genres=genres or [],
    )


def _make_entry(
    user_id: str,
    album_id: str,
    *,
    rating: float | None = None,
    logged_at: datetime | None = None,
) -> DiaryEntry:
    return DiaryEntry(
        user_id=user_id,
        album_id=album_id,
        logged_at=logged_at or datetime.now(UTC),
        rating=rating,
        visibility=Visibility.PUBLIC,
    )


@pytest_asyncio.fixture
async def _clean_db() -> AsyncIterator[None]:
    await Suggestion.delete_all()
    await SuggestionDismissal.delete_all()
    await Follow.delete_all()
    await Block.delete_all()
    await User.delete_all()
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await CriticSeed.delete_all()
    yield
    await Suggestion.delete_all()
    await SuggestionDismissal.delete_all()
    await Follow.delete_all()
    await Block.delete_all()
    await User.delete_all()
    await Album.delete_all()
    await DiaryEntry.delete_all()
    await CriticSeed.delete_all()


# ---------------------------------------------------------------------------
# Pure scoring tests — no DB needed.
# ---------------------------------------------------------------------------


def test_score_candidate_zero_signals_returns_zero() -> None:
    """All signals empty → final score is 0, reasons list empty."""
    result = score_candidate(
        mutual_taste_overlap=0.0,
        followed_by_followed_count=0,
        followed_by_followed_total=0,
        shared_seed=False,
        label_genre_overlap=False,
        recent_activity=False,
    )
    assert result.score == 0.0
    assert result.reasons == []


def test_score_candidate_mutual_taste_only_contributes_40() -> None:
    """Full mutual-taste overlap with no other signal → score == 0.40."""
    result = score_candidate(
        mutual_taste_overlap=1.0,
        followed_by_followed_count=0,
        followed_by_followed_total=0,
        shared_seed=False,
        label_genre_overlap=False,
        recent_activity=False,
    )
    assert result.score == pytest.approx(WEIGHT_MUTUAL_TASTE)
    assert result.reasons == ["mutual_taste"]


def test_score_candidate_followed_by_followed_only_contributes_30() -> None:
    """All viewer's followees follow the candidate → score == 0.30."""
    result = score_candidate(
        mutual_taste_overlap=0.0,
        followed_by_followed_count=5,
        followed_by_followed_total=5,
        shared_seed=False,
        label_genre_overlap=False,
        recent_activity=False,
    )
    assert result.score == pytest.approx(WEIGHT_FOLLOWED_BY_FOLLOWED)
    assert result.reasons == ["followed_by_followed"]


def test_score_candidate_shared_seed_only_contributes_15() -> None:
    """Shared seed only → score == 0.15."""
    result = score_candidate(
        mutual_taste_overlap=0.0,
        followed_by_followed_count=0,
        followed_by_followed_total=0,
        shared_seed=True,
        label_genre_overlap=False,
        recent_activity=False,
    )
    assert result.score == pytest.approx(WEIGHT_SHARED_SEED)
    assert result.reasons == ["shared_seed"]


def test_score_candidate_full_mix_sums_all_weights() -> None:
    """Every signal at max → score == 1.0 with all five reason tags."""
    result = score_candidate(
        mutual_taste_overlap=1.0,
        followed_by_followed_count=10,
        followed_by_followed_total=10,
        shared_seed=True,
        label_genre_overlap=True,
        recent_activity=True,
    )
    # The weights are designed to sum to exactly 1.0; allow a tiny
    # floating-point epsilon so the test doesn't drift on later weight
    # tweaks.
    assert result.score == pytest.approx(
        WEIGHT_MUTUAL_TASTE
        + WEIGHT_FOLLOWED_BY_FOLLOWED
        + WEIGHT_SHARED_SEED
        + WEIGHT_LABEL_GENRE
        + WEIGHT_RECENCY
    )
    assert result.reasons == [
        "mutual_taste",
        "followed_by_followed",
        "shared_seed",
        "label_genre",
        "recency",
    ]


def test_score_candidate_partial_followed_ratio_scales() -> None:
    """Half the viewer's followees follow the candidate → contrib is half-weight."""
    result = score_candidate(
        mutual_taste_overlap=0.0,
        followed_by_followed_count=5,
        followed_by_followed_total=10,
        shared_seed=False,
        label_genre_overlap=False,
        recent_activity=False,
    )
    assert result.score == pytest.approx(WEIGHT_FOLLOWED_BY_FOLLOWED * 0.5)
    assert result.reasons == ["followed_by_followed"]


def test_score_candidate_mutual_taste_clamped_to_one() -> None:
    """An out-of-range overlap value never exceeds its weight contribution."""
    # Defence-in-depth check: a buggy caller passing 2.0 should not
    # blow the [0,1] final score contract.
    result = score_candidate(
        mutual_taste_overlap=2.0,
        followed_by_followed_count=0,
        followed_by_followed_total=0,
        shared_seed=False,
        label_genre_overlap=False,
        recent_activity=False,
    )
    assert result.score == pytest.approx(WEIGHT_MUTUAL_TASTE)


# ---------------------------------------------------------------------------
# End-to-end worker tests against the in-memory mongomock DB.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_suggestions_excludes_already_followed(_clean_db: None) -> None:
    """A user the viewer already follows is never a candidate."""
    viewer = _make_user("user-viewer", "viewer")
    bob = _make_user("user-bob", "bob")
    await viewer.insert()
    await bob.insert()

    # Make bob a strong candidate via shared seeds + recent activity.
    seed = _make_user("user-seed", "criticone")
    await seed.insert()
    await CriticSeed(user_id=seed.id, priority=80, active=True).insert()
    for follower in (viewer, bob):
        await Follow(
            follower_id=follower.id,
            followee_id=seed.id,
            state=FollowState.ACCEPTED,
        ).insert()
    album = _make_album("album-rec")
    await album.insert()
    await _make_entry(bob.id, album.id, rating=5.0, logged_at=datetime.now(UTC)).insert()

    # Now also follow bob directly — this should exclude him.
    await Follow(
        follower_id=viewer.id,
        followee_id=bob.id,
        state=FollowState.ACCEPTED,
    ).insert()

    count = await compute_suggestions_for_user(viewer.id)
    assert count == 0
    rows = await Suggestion.find({"user_id": viewer.id}).to_list()
    assert rows == []


@pytest.mark.asyncio
async def test_compute_suggestions_excludes_blocked_either_direction(
    _clean_db: None,
) -> None:
    """Blocked users (either direction) are not suggested even with strong signals."""
    viewer = _make_user("user-viewer", "viewer")
    bob = _make_user("user-bob", "bob")
    carol = _make_user("user-carol", "carol")
    await viewer.insert()
    await bob.insert()
    await carol.insert()

    # Both bob + carol have strong recent activity.
    album = _make_album("album-act", genres=["indie"])
    await album.insert()
    now = datetime.now(UTC)
    for user_id in (bob.id, carol.id):
        await _make_entry(user_id, album.id, rating=5.0, logged_at=now).insert()
    # Viewer also liked the album so mutual-taste fires.
    await _make_entry(viewer.id, album.id, rating=5.0, logged_at=now).insert()

    # viewer → bob block; carol → viewer block. Both must be excluded.
    await Block(
        blocker_id=viewer.id,
        blockee_id=bob.id,
        reason=BlockReason.HARASSMENT,
    ).insert()
    await Block(
        blocker_id=carol.id,
        blockee_id=viewer.id,
        reason=BlockReason.SPAM,
    ).insert()

    await compute_suggestions_for_user(viewer.id)
    rows = await Suggestion.find({"user_id": viewer.id}).to_list()
    suggested_ids = {row.suggested_user_id for row in rows}
    assert bob.id not in suggested_ids
    assert carol.id not in suggested_ids


@pytest.mark.asyncio
async def test_compute_suggestions_excludes_dismissed_within_30_days(
    _clean_db: None,
) -> None:
    """Dismissed candidates stay out of the suggestion set while the TTL row lives."""
    viewer = _make_user("user-viewer", "viewer")
    bob = _make_user("user-bob", "bob")
    await viewer.insert()
    await bob.insert()

    album = _make_album("album-dis")
    await album.insert()
    await _make_entry(bob.id, album.id, rating=5.0, logged_at=datetime.now(UTC)).insert()
    await _make_entry(viewer.id, album.id, rating=5.0, logged_at=datetime.now(UTC)).insert()

    # Active dismissal — dismissed_at is well within the 30-day window.
    await SuggestionDismissal(
        user_id=viewer.id,
        suggested_user_id=bob.id,
        dismissed_at=datetime.now(UTC) - timedelta(days=5),
    ).insert()

    await compute_suggestions_for_user(viewer.id)
    rows = await Suggestion.find({"user_id": viewer.id}).to_list()
    assert all(row.suggested_user_id != bob.id for row in rows)


@pytest.mark.asyncio
async def test_compute_suggestions_full_mix_writes_score_and_reasons(
    _clean_db: None,
) -> None:
    """A candidate with every signal firing scores ~1.0 and lists every reason."""
    viewer = _make_user("user-viewer", "viewer")
    bob = _make_user("user-bob", "bob")
    friend = _make_user("user-friend", "friend")
    seed = _make_user("user-seed", "criticone")
    await viewer.insert()
    await bob.insert()
    await friend.insert()
    await seed.insert()
    await CriticSeed(user_id=seed.id, priority=80, active=True).insert()

    # 1. Mutual-taste: viewer and bob both rated the same album 5.0.
    album1 = _make_album("album-mut", label="Big Indie", genres=["indie"])
    await album1.insert()
    now = datetime.now(UTC)
    await _make_entry(viewer.id, album1.id, rating=5.0, logged_at=now).insert()
    await _make_entry(bob.id, album1.id, rating=5.0, logged_at=now).insert()

    # 2. Followed-by-followed: viewer follows friend, friend follows bob.
    await Follow(
        follower_id=viewer.id,
        followee_id=friend.id,
        state=FollowState.ACCEPTED,
    ).insert()
    await Follow(
        follower_id=friend.id,
        followee_id=bob.id,
        state=FollowState.ACCEPTED,
    ).insert()

    # 3. Shared-seed: viewer + bob both follow the critic-seed account.
    for follower in (viewer, bob):
        await Follow(
            follower_id=follower.id,
            followee_id=seed.id,
            state=FollowState.ACCEPTED,
        ).insert()

    # 4. Label/genre: album1 already has shared label + genre; both
    #    users' top-5 contains it.
    # 5. Recency: bob has logged within the last 30 days (now).

    await compute_suggestions_for_user(viewer.id)
    rows = await Suggestion.find({"user_id": viewer.id}).to_list()
    bob_row = next((row for row in rows if row.suggested_user_id == bob.id), None)
    assert bob_row is not None
    # Every reason tag should appear.
    assert set(bob_row.reasons) == {
        "mutual_taste",
        "followed_by_followed",
        "shared_seed",
        "label_genre",
        "recency",
    }
    # Score is the sum of weights with FBF scaled by ratio of viewer's
    # followees who also follow bob. The viewer follows {friend, seed};
    # only friend follows bob → FBF ratio = 0.5.
    expected = (
        WEIGHT_MUTUAL_TASTE
        + WEIGHT_FOLLOWED_BY_FOLLOWED * 0.5
        + WEIGHT_SHARED_SEED
        + WEIGHT_LABEL_GENRE
        + WEIGHT_RECENCY
    )
    assert bob_row.score == pytest.approx(expected)


@pytest.mark.asyncio
async def test_compute_suggestions_mutual_taste_only(_clean_db: None) -> None:
    """A candidate with ONLY mutual-taste fires the mutual_taste reason and its weight."""
    viewer = _make_user("user-viewer", "viewer")
    bob = _make_user("user-bob", "bob")
    await viewer.insert()
    await bob.insert()

    # Use a much older log so the recency boost doesn't fire.
    album = _make_album("album-mut-only")
    await album.insert()
    old = datetime.now(UTC) - timedelta(days=120)
    await _make_entry(viewer.id, album.id, rating=5.0, logged_at=old).insert()
    await _make_entry(bob.id, album.id, rating=5.0, logged_at=old).insert()

    await compute_suggestions_for_user(viewer.id)
    rows = await Suggestion.find({"user_id": viewer.id}).to_list()
    bob_row = next((row for row in rows if row.suggested_user_id == bob.id), None)
    assert bob_row is not None
    assert "mutual_taste" in bob_row.reasons
    assert "recency" not in bob_row.reasons
    # No followees, no critic-seed, no labels — mutual_taste +
    # label_genre should be the only non-zero contributions.
    # Both users' top-5 has the same album, so labels/genres are
    # shared (even though the album has none defined → set is empty
    # → no label/genre tag).
    assert "followed_by_followed" not in bob_row.reasons
    assert "shared_seed" not in bob_row.reasons


@pytest.mark.asyncio
async def test_compute_suggestions_followed_by_followed_only(
    _clean_db: None,
) -> None:
    """Followed-by-followed signal alone produces that reason + its weight."""
    viewer = _make_user("user-viewer", "viewer")
    friend = _make_user("user-friend", "friend")
    bob = _make_user("user-bob", "bob")
    await viewer.insert()
    await friend.insert()
    await bob.insert()

    await Follow(
        follower_id=viewer.id,
        followee_id=friend.id,
        state=FollowState.ACCEPTED,
    ).insert()
    await Follow(
        follower_id=friend.id,
        followee_id=bob.id,
        state=FollowState.ACCEPTED,
    ).insert()

    await compute_suggestions_for_user(viewer.id)
    rows = await Suggestion.find({"user_id": viewer.id}).to_list()
    bob_row = next((row for row in rows if row.suggested_user_id == bob.id), None)
    assert bob_row is not None
    assert "followed_by_followed" in bob_row.reasons
    assert bob_row.score == pytest.approx(WEIGHT_FOLLOWED_BY_FOLLOWED)


@pytest.mark.asyncio
async def test_compute_suggestions_shared_seed_only(_clean_db: None) -> None:
    """Shared-seed alone surfaces the shared_seed reason + its weight."""
    viewer = _make_user("user-viewer", "viewer")
    bob = _make_user("user-bob", "bob")
    seed = _make_user("user-seed", "criticone")
    await viewer.insert()
    await bob.insert()
    await seed.insert()
    await CriticSeed(user_id=seed.id, priority=80, active=True).insert()

    for follower in (viewer, bob):
        await Follow(
            follower_id=follower.id,
            followee_id=seed.id,
            state=FollowState.ACCEPTED,
        ).insert()

    await compute_suggestions_for_user(viewer.id)
    rows = await Suggestion.find({"user_id": viewer.id}).to_list()
    bob_row = next((row for row in rows if row.suggested_user_id == bob.id), None)
    assert bob_row is not None
    assert "shared_seed" in bob_row.reasons
    # Note that viewer also follows seed, so seed itself is excluded;
    # bob has followed-by-followed = 0 here (viewer's only followee is
    # seed and seed doesn't follow bob). Score should be exactly
    # WEIGHT_SHARED_SEED.
    assert bob_row.score == pytest.approx(WEIGHT_SHARED_SEED)


@pytest.mark.asyncio
async def test_compute_suggestions_clears_stale_rows(_clean_db: None) -> None:
    """Re-running the worker rewrites the suggestion set from scratch."""
    viewer = _make_user("user-viewer", "viewer")
    bob = _make_user("user-bob", "bob")
    await viewer.insert()
    await bob.insert()

    # Seed a stale row that no longer matches any real signal.
    await Suggestion(
        user_id=viewer.id,
        suggested_user_id=bob.id,
        score=0.9,
        reasons=["stale_signal"],
    ).insert()

    await compute_suggestions_for_user(viewer.id)
    rows = await Suggestion.find({"user_id": viewer.id}).to_list()
    # No signal fires → stale row should be cleared, no replacement.
    assert rows == []
