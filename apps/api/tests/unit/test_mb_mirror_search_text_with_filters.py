"""Unit tests for :meth:`AlbumMirrorService.search_text_with_filters`.

Mocks the underlying :class:`TursoClient` to capture the SQL +
parameter binding shape without spinning up a real Turso database.
The combined MATCH + WHERE path is the new code surface from
feature 004 — these tests pin its public contract:

* Empty query returns ``([], 0)`` without hitting the network.
* Disabled mirror returns ``([], 0)``.
* Filter intersections (decade + year_max) bind correctly.
* sort_key variants pick the right ORDER BY clause.
* COUNT capping at ``_TOTAL_DISPLAY_CAP`` (10,000).
* surprise mode skips the COUNT and uses ``ORDER BY RANDOM()``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from auxd_api.modules.mb_mirror.client import StatementResult
from auxd_api.modules.mb_mirror.service import AlbumMirrorService


def _result(rows: list[list[Any]], columns: list[str] | None = None) -> StatementResult:
    return StatementResult(columns=columns or [], rows=rows)


@pytest.mark.asyncio
async def test_disabled_mirror_returns_empty() -> None:
    service = AlbumMirrorService(client=None)
    rows, total = await service.search_text_with_filters(
        query="kanye west",
        year_min=None,
        year_max=None,
        decade_buckets=None,
        genre=None,
        sort_key="relevance",
        limit=50,
        offset=0,
    )
    assert rows == []
    assert total == 0


@pytest.mark.asyncio
async def test_empty_query_returns_empty() -> None:
    # FTS5 needs a non-empty MATCH expression; blank input short-circuits.
    client = AsyncMock()
    service = AlbumMirrorService(client=client)
    rows, total = await service.search_text_with_filters(
        query="   ",
        year_min=None,
        year_max=None,
        decade_buckets=None,
        genre=None,
        sort_key="relevance",
        limit=50,
        offset=0,
    )
    assert rows == []
    assert total == 0
    client.execute.assert_not_called()


@pytest.mark.asyncio
async def test_relevance_sort_uses_rank() -> None:
    """sort_key='relevance' triggers ``ORDER BY rank`` (FTS5 BM25)."""
    client = AsyncMock()
    client.execute.side_effect = [
        _result([[42]]),  # count
        _result(
            [
                [
                    "mbid-1",
                    "Jesus Is King",
                    "Kanye West",
                    2019,
                    "Album",
                    "hip hop",
                    None,
                ]
            ]
        ),
    ]
    service = AlbumMirrorService(client=client)
    rows, total = await service.search_text_with_filters(
        query="kanye",
        year_min=None,
        year_max=None,
        decade_buckets=None,
        genre=None,
        sort_key="relevance",
        limit=50,
        offset=0,
    )
    assert total == 42
    assert len(rows) == 1
    assert rows[0].title == "Jesus Is King"
    # The page query should have ORDER BY rank.
    page_sql = client.execute.call_args_list[1].args[0]
    assert "ORDER BY rank" in page_sql


@pytest.mark.asyncio
async def test_count_capped_at_display_cap() -> None:
    """A COUNT > 10,000 is clamped to ``_TOTAL_DISPLAY_CAP`` per FR-008."""
    client = AsyncMock()
    client.execute.side_effect = [
        _result([[12_500]]),  # huge count
        _result([]),
    ]
    service = AlbumMirrorService(client=client)
    _rows, total = await service.search_text_with_filters(
        query="the",
        year_min=None,
        year_max=None,
        decade_buckets=None,
        genre=None,
        sort_key="relevance",
        limit=50,
        offset=0,
    )
    assert total == 10_000


@pytest.mark.asyncio
async def test_decade_and_year_max_filter_intersect_in_where() -> None:
    """decade=2010s + year_max=2012 → effective range 2010..2012 in BETWEEN."""
    client = AsyncMock()
    client.execute.side_effect = [_result([[3]]), _result([])]
    service = AlbumMirrorService(client=client)
    await service.search_text_with_filters(
        query="kanye",
        year_min=None,
        year_max=2012,
        decade_buckets={2010},
        genre=None,
        sort_key="relevance",
        limit=50,
        offset=0,
    )
    # Both the count and page queries should bind the effective
    # year range [2010, 2012] following the FTS5 match param.
    count_params = client.execute.call_args_list[0].kwargs["params"]
    assert count_params[0].startswith("kanye")  # FTS match expr
    assert 2010 in count_params and 2012 in count_params


@pytest.mark.asyncio
async def test_surprise_sort_uses_random_no_count() -> None:
    """sort_key='surprise' uses ORDER BY RANDOM() and returns len(rows) as total."""
    client = AsyncMock()
    client.execute.return_value = _result([["mbid-1", "Random", "Artist", 2020, "Album", "", None]])
    service = AlbumMirrorService(client=client)
    rows, total = await service.search_text_with_filters(
        query="kanye",
        year_min=None,
        year_max=None,
        decade_buckets=None,
        genre=None,
        sort_key="surprise",
        limit=10,
        offset=0,
    )
    assert total == len(rows) == 1
    # Surprise does ONE query (no separate COUNT).
    assert client.execute.call_count == 1
    sql = client.execute.call_args.args[0]
    assert "RANDOM()" in sql


@pytest.mark.asyncio
async def test_year_newest_sort_uses_release_year_desc() -> None:
    client = AsyncMock()
    client.execute.side_effect = [_result([[0]]), _result([])]
    service = AlbumMirrorService(client=client)
    await service.search_text_with_filters(
        query="kanye",
        year_min=None,
        year_max=None,
        decade_buckets=None,
        genre=None,
        sort_key="year_newest",
        limit=50,
        offset=0,
    )
    page_sql = client.execute.call_args_list[1].args[0]
    assert "release_year DESC" in page_sql


@pytest.mark.asyncio
async def test_impossible_year_decade_intersection_returns_empty() -> None:
    """decade=2010s + year_max=1999 has no overlap → ``([], 0)`` without SQL."""
    client = AsyncMock()
    service = AlbumMirrorService(client=client)
    rows, total = await service.search_text_with_filters(
        query="kanye",
        year_min=None,
        year_max=1999,
        decade_buckets={2010},
        genre=None,
        sort_key="relevance",
        limit=50,
        offset=0,
    )
    assert rows == []
    assert total == 0
    client.execute.assert_not_called()
