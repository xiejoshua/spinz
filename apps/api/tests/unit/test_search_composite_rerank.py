"""Unit tests for the composite reranker (feature 004).

Pins the four fixture queries from the spec (kanye west, frank ocean,
kanye graduation, graduation) with explicit input rows + asserted
output orderings, plus the token-coverage edge cases the implementation
relies on.
"""

from __future__ import annotations

from typing import Any

from auxd_api.modules.search.service import (
    _composite_rerank,
    _coverage_ratio,
    _tokenize,
)


def _hit(
    *,
    title: str,
    artist: str,
    rating_count: int = 0,
    mbid: str | None = None,
) -> dict[str, Any]:
    return {
        "mbid": mbid or f"mbid-{title.lower().replace(' ', '-')}",
        "title": title,
        "artist_name": artist,
        "rating_count": rating_count,
    }


# ---------- tokenize / coverage helpers ----------


def test_tokenize_strips_stopwords_and_casefolds() -> None:
    assert _tokenize("The Kanye West") == {"kanye", "west"}
    assert _tokenize("A & B and Friends") == {"b", "friends"}


def test_tokenize_empty_returns_empty_set() -> None:
    assert _tokenize("") == set()
    assert _tokenize("   ") == set()


def test_tokenize_strips_punctuation() -> None:
    """004 follow-up regression: commas/dots/parens must not glue onto
    adjacent letters. 'Tyler, The Creator' must tokenise as
    ``{tyler, creator}`` so a 'tyler the creator' query reaches the
    coverage threshold. Pre-fix, this returned ``{"tyler,", "creator"}``
    which dropped coverage to 0.5 and silently disabled the rerank
    boost for that artist.
    """
    assert _tokenize("Tyler, The Creator") == {"tyler", "creator"}
    assert _tokenize("Earth, Wind & Fire") == {"earth", "wind", "fire"}
    assert _tokenize("Wu-Tang Clan") == {"wu", "tang", "clan"}
    assert _tokenize("Florence + The Machine") == {"florence", "machine"}


def test_tokenize_preserves_unicode_letters() -> None:
    """Non-ASCII characters survive — Björk, Beyoncé, etc."""
    assert _tokenize("Björk") == {"björk"}
    assert _tokenize("Beyoncé") == {"beyoncé"}
    assert _tokenize("Sigur Rós") == {"sigur", "rós"}


def test_coverage_empty_query_or_target_is_zero() -> None:
    assert _coverage_ratio(set(), {"kanye"}) == 0.0
    assert _coverage_ratio({"kanye"}, set()) == 0.0


def test_coverage_single_token_match_is_full() -> None:
    # "kanye" against "kanye west" → 1 / min(1, 2) == 1.0.
    assert _coverage_ratio({"kanye"}, {"kanye", "west"}) == 1.0


def test_coverage_no_overlap_is_zero() -> None:
    assert _coverage_ratio({"kanye"}, {"tyler", "creator"}) == 0.0


# ---------- composite rerank: 4 fixture queries ----------


def test_kanye_west_lifts_kanye_albums_above_credit_match() -> None:
    """Spec US-002: q='kanye west' → Jesus Is King > Igor.

    Igor arrives at BM25 position 0 (Discogs popularity surfaced it),
    but its artist 'Tyler, the Creator' fails the coverage threshold
    against the query tokens {kanye, west}, so it stays at score 2.
    Jesus Is King (artist='Kanye West') gets +10 boost, lifting it
    above Igor at score 11.
    """
    candidates = [
        _hit(title="Igor", artist="Tyler, the Creator", rating_count=5000),
        _hit(title="Jesus Is King", artist="Kanye West", rating_count=2000),
    ]
    out = _composite_rerank(candidates, query="kanye west")
    assert out[0]["title"] == "Jesus Is King"
    assert out[1]["title"] == "Igor"


def test_kanye_west_top_5_contains_4_kanye_albums() -> None:
    """Spec success criterion: top-5 must contain ≥4 Kanye West albums."""
    candidates = [
        _hit(title="Igor", artist="Tyler, the Creator", rating_count=5000),
        _hit(title="Some Compilation", artist="Various Artists", rating_count=200),
        _hit(title="Graduation", artist="Kanye West", rating_count=4000),
        _hit(title="808s & Heartbreak", artist="Kanye West", rating_count=3000),
        _hit(title="Jesus Is King", artist="Kanye West", rating_count=2000),
        _hit(title="My Beautiful Dark Twisted Fantasy", artist="Kanye West", rating_count=5000),
    ]
    out = _composite_rerank(candidates, query="kanye west")
    top5_artists = [hit["artist_name"] for hit in out[:5]]
    kanye_count = sum(1 for a in top5_artists if a == "Kanye West")
    assert kanye_count >= 4


def test_kanye_albums_tiebreak_by_rating_count() -> None:
    """When two Kanye albums tie on composite score, rating_count breaks."""
    candidates = [
        _hit(title="Graduation", artist="Kanye West", rating_count=4000),
        _hit(title="808s & Heartbreak", artist="Kanye West", rating_count=3000),
    ]
    out = _composite_rerank(candidates, query="kanye west")
    # Graduation has higher rating_count → first.
    assert out[0]["title"] == "Graduation"
    assert out[1]["title"] == "808s & Heartbreak"


def test_frank_ocean_brings_own_discography_above_compilation() -> None:
    """Spec US-002: q='frank ocean' → Blonde / Channel Orange before
    a compilation appearance.
    """
    candidates = [
        _hit(
            title="The Best of R&B", artist="Various Artists", rating_count=8000
        ),  # popular compilation
        _hit(title="Blonde", artist="Frank Ocean", rating_count=4000),
        _hit(title="Channel Orange", artist="Frank Ocean", rating_count=3500),
    ]
    out = _composite_rerank(candidates, query="frank ocean")
    assert out[0]["artist_name"] == "Frank Ocean"
    assert out[1]["artist_name"] == "Frank Ocean"
    assert out[-1]["title"] == "The Best of R&B"


def test_mixed_query_kanye_graduation_top_hit_is_graduation() -> None:
    """Spec US-003: q='kanye graduation' → Graduation by Kanye at top.

    Mirror's FTS5 multi-token AND already prioritises the album that
    matches BOTH tokens; the composite reranker only further reinforces
    by lifting the artist-match score.
    """
    candidates = [
        _hit(title="Graduation", artist="Kanye West", rating_count=4000),
        _hit(title="My Beautiful Dark Twisted Fantasy", artist="Kanye West", rating_count=5000),
    ]
    out = _composite_rerank(candidates, query="kanye graduation")
    # Both artists pass coverage; sort then on (score, rating_count)
    # but BM25 base score keeps Graduation (which mirror put first
    # for both-token match) on top — index 0 in input → highest base.
    assert out[0]["title"] == "Graduation"


def test_title_only_query_still_works() -> None:
    """Spec US-002 acceptance: q='graduation' (single title token)
    finds the album. With single-token coverage the artist boost only
    fires if 'graduation' is in the artist credit — it isn't, so the
    BM25 base order wins (which already had Graduation first).
    """
    candidates = [
        _hit(title="Graduation", artist="Kanye West", rating_count=4000),
        _hit(title="Other Album", artist="Other Artist", rating_count=10000),
    ]
    out = _composite_rerank(candidates, query="graduation")
    assert out[0]["title"] == "Graduation"


def test_empty_candidates_returns_empty() -> None:
    assert _composite_rerank([], query="anything") == []


def test_empty_query_preserves_order() -> None:
    """Empty query → no token coverage check fires → mirror BM25 order
    survives, modulated only by rating_count tiebreak (which would
    still kick in on equal base scores; here all base scores differ).
    """
    candidates = [
        _hit(title="First", artist="A"),
        _hit(title="Second", artist="B"),
    ]
    out = _composite_rerank(candidates, query="")
    assert [hit["title"] for hit in out] == ["First", "Second"]


def test_empty_artist_does_not_crash() -> None:
    candidates = [_hit(title="No Artist", artist="")]
    out = _composite_rerank(candidates, query="kanye")
    assert len(out) == 1


# ---------- 004 follow-up: hard-bucket invariant ----------


def test_tyler_the_creator_lifts_tyler_above_channel_orange() -> None:
    """004 follow-up: q='tyler the creator' must NEVER return Frank Ocean's
    Channel Orange (where Tyler is a credited producer) before Tyler's
    own albums. The previous additive +10 boost was too soft — Channel
    Orange's BM25/popularity put it at index 0, +10 wasn't enough to
    overcome the gap. With two-bucket rerank, the hard partition
    enforces 'artist match → always above non-match' regardless of
    input position.
    """
    candidates = [
        # Source ordering deliberately puts Channel Orange first
        # (mimicking Discogs popularity ranking it ahead of Tyler's
        # own discography because Tyler is a credit on the album).
        _hit(title="Channel Orange", artist="Frank Ocean", rating_count=8000),
        _hit(title="Igor", artist="Tyler, The Creator", rating_count=4000),
        _hit(title="Flower Boy", artist="Tyler, The Creator", rating_count=3500),
        _hit(title="Call Me If You Get Lost", artist="Tyler, The Creator", rating_count=2000),
    ]
    out = _composite_rerank(candidates, query="tyler the creator")
    artists = [hit["artist_name"] for hit in out]
    # First three are Tyler's albums.
    assert artists[:3] == ["Tyler, The Creator"] * 3
    # Channel Orange demoted to the bottom.
    assert artists[-1] == "Frank Ocean"


def test_hard_bucket_invariant_no_match_can_outrank_match() -> None:
    """Stronger version of the Tyler invariant: even if a non-matching
    candidate has overwhelmingly higher rating_count AND sits at index 0
    of the source order, it MUST land below any artist-match.
    """
    candidates = [
        # Non-match, sits at top of source order with huge popularity.
        _hit(title="Massive Hit", artist="Some Other Artist", rating_count=1_000_000),
        # Match, last in source order with low popularity.
        _hit(title="Obscure Track", artist="Kanye West", rating_count=10),
    ]
    out = _composite_rerank(candidates, query="kanye west")
    assert out[0]["title"] == "Obscure Track"
    assert out[1]["title"] == "Massive Hit"
