"""Edition aggregation service (T066).

MusicBrainz organises albums into *release-groups* (the abstract work,
e.g. "Kid A") and *releases* (the concrete pressings — Standard, Deluxe,
Bonus, Anniversary). The UI surface for the auxd MVP only needs the
release-group view: pick an album, show every edition, aggregate the
social signal across all of them.

Per-release MBIDs are deferred:
    The MVP stores release-group MBIDs in ``Album.mbid`` (with a
    unique-sparse index) and does NOT materialise sibling releases as
    their own :class:`Album` rows. The :data:`Album.editions` subdoc
    list captures sibling release references that the album-detail
    endpoint surfaces inline; for "All editions" rollup purposes the
    MVP collapses the entire release-group to the single :class:`Album`
    row carrying the MBID.

    When a future task surfaces per-release MBIDs we'll add a
    ``release_group_mbid`` field, drop the unique constraint on ``mbid``,
    and migrate; the queries here will at that point return the full
    sibling set without code changes.

Three operations:

* :func:`get_editions` — every Album sharing a release-group MBID
  (currently a single-element list at MVP, see above).
* :func:`get_canonical_edition` — the "default" edition shown when the
  user hasn't picked one (earliest year, then longest tracklist).
* :func:`aggregate_ratings` — DiaryEntry + Review counts/averages
  summed across every edition for the album-detail "social signal" row.
"""

from __future__ import annotations

from auxd_api.modules.albums.models import Album
from auxd_api.modules.diary.models import DiaryEntry
from auxd_api.modules.reviews.models import Review, ReviewLike


async def get_editions(release_group_mbid: str) -> list[Album]:
    """Return every :class:`Album` carrying the given release-group MBID.

    Deduplicates on the ``(title, artist_credit, primary_type,
    release_year)`` tuple — see module docstring. The MVP catalog rarely
    has duplicates but a future ingestion bug could insert two rows for
    the same pressing; the dedupe keeps the UI stable in that case.

    Ordering: oldest first by ``release_year``, ``None`` years sort last
    so unreleased / undated rows don't push the canonical pressing down
    the list.
    """
    rows = await Album.find(Album.mbid == release_group_mbid).sort("+release_year").to_list()
    seen: set[tuple[str, str, int | None]] = set()
    deduped: list[Album] = []
    for album in rows:
        key = (album.title, album.artist_credit, album.release_year)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(album)
    return deduped


async def get_canonical_edition(release_group_mbid: str) -> Album | None:
    """Return the canonical edition for a release-group, or ``None`` if none exist.

    Preference order: earliest ``release_year``, then longest tracklist.
    The earliest year captures "original pressing" intent; the tracklist
    tiebreak picks the more complete edition when two share a year (the
    Deluxe usually wins over the Standard when timestamps tie).
    """
    editions = await get_editions(release_group_mbid)
    if not editions:
        return None
    return min(
        editions,
        key=lambda album: (
            # release_year=None sorts AFTER any concrete year by using
            # a sentinel larger than any plausible year value.
            album.release_year if album.release_year is not None else 9999,
            # Negative length so the *longer* tracklist wins the
            # min() tiebreak (min picks the smaller value).
            -len(album.tracklist),
        ),
    )


async def aggregate_ratings(release_group_mbid: str) -> dict[str, float | int]:
    """Return the social-signal rollup for every edition in a release-group.

    Sums ``DiaryEntry`` rating counts + averages, ``Review`` counts, Aux
    counts (``DiaryEntry.auxed=True``), and ``ReviewLike`` counts across
    every edition. An empty release-group (or one with no diary activity
    yet) returns zeros for every field — callers can render the row
    without a defensive ``if not aggregate``.
    """
    editions = await get_editions(release_group_mbid)
    if not editions:
        return {
            "avg_rating": 0.0,
            "rating_count": 0,
            "review_count": 0,
            "aux_count": 0,
            "like_count": 0,
        }
    album_ids = [album.id for album in editions]

    diary_entries = await DiaryEntry.find(
        {"album_id": {"$in": album_ids}, "deleted_at": None}
    ).to_list()
    ratings = [entry.rating for entry in diary_entries if entry.rating is not None]
    rating_count = len(ratings)
    avg_rating = (sum(ratings) / rating_count) if rating_count else 0.0
    aux_count = sum(1 for entry in diary_entries if entry.auxed)

    reviews = await Review.find({"album_id": {"$in": album_ids}}).to_list()
    review_count = len(reviews)

    review_ids = [review.id for review in reviews]
    if review_ids:
        like_count = await ReviewLike.find({"review_id": {"$in": review_ids}}).count()
    else:
        like_count = 0

    return {
        "avg_rating": round(avg_rating, 2),
        "rating_count": rating_count,
        "review_count": review_count,
        "aux_count": aux_count,
        "like_count": like_count,
    }


__all__ = [
    "aggregate_ratings",
    "get_canonical_edition",
    "get_editions",
]
