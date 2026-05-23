"""Smoke tests for the Atlas Search index definition (T068).

The index JSON is applied out-of-band via the Atlas UI or ``atlas-cli``;
these tests guard the document shape so that an accidental edit
(missing analyzer, deleted edgeNgram block, dropped ``rating_count``
indexing for future popularity boosts) fails CI before it lands in
the migrations runbook.

We deliberately do NOT attempt to apply the index against mongomock —
mongomock doesn't implement ``$search`` at all. The route-layer
``_atlas_search`` helper falls back to an empty list when ``$search`` is
unavailable, so the system stays testable without a real Atlas
cluster.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

_INDEX_PATH = (
    Path(__file__).resolve().parents[2] / "migrations" / "atlas_search" / "albums_index.json"
)


@pytest.fixture(scope="module")
def index_doc() -> dict[str, Any]:
    """Load the Atlas Search index JSON once per test module."""
    with _INDEX_PATH.open() as fp:
        return cast(dict[str, Any], json.load(fp))


def test_index_has_canonical_name(index_doc: dict[str, Any]) -> None:
    """The index name is the wire contract for ``$search.index`` calls."""
    assert index_doc["name"] == "albums_text_search"


def test_definition_has_lucene_standard_analyzer(index_doc: dict[str, Any]) -> None:
    """Top-level analyzer is ``lucene.standard``."""
    definition = index_doc["definition"]
    assert isinstance(definition, dict)
    assert definition["analyzer"] == "lucene.standard"
    assert definition["searchAnalyzer"] == "lucene.standard"


def test_definition_indexes_title_with_autocomplete(
    index_doc: dict[str, Any],
) -> None:
    """``title`` must carry both ``string`` and ``autocomplete`` field shapes."""
    fields = index_doc["definition"]["mappings"]["fields"]
    title_fields = fields["title"]
    assert isinstance(title_fields, list)
    assert {entry["type"] for entry in title_fields} == {"string", "autocomplete"}
    autocomplete = next(entry for entry in title_fields if entry["type"] == "autocomplete")
    assert autocomplete["tokenization"] == "edgeGram"
    assert autocomplete["minGrams"] == 2
    assert autocomplete["maxGrams"] == 8


def test_definition_indexes_artist_credit_with_autocomplete(
    index_doc: dict[str, Any],
) -> None:
    """``artist_credit`` autocomplete uses the same edgeNgram parameters."""
    fields = index_doc["definition"]["mappings"]["fields"]
    artist_fields = fields["artist_credit"]
    assert isinstance(artist_fields, list)
    assert any(entry["type"] == "autocomplete" for entry in artist_fields)


def test_definition_indexes_rating_count_for_future_popularity_boost(
    index_doc: dict[str, Any],
) -> None:
    """``rating_count`` is indexed as a numeric field so a future query-time
    popularity boost can reference it.

    NOTE: the popularity boost itself is applied at QUERY time (in a
    ``$search`` compound stage with a ``function`` score clause), not at
    index-definition time. An earlier draft of this index put the
    log1p(rating_count) function inside a top-level ``scoreDetails``
    block — Atlas Search rejects that as an invalid index-definition
    field (``scoreDetails`` is a query-level parameter), with a
    misleading "Please define the mappings document" error from the UI
    validator. ``modules/search/service.py`` is where the boost lands
    when wired up.
    """
    fields = index_doc["definition"]["mappings"]["fields"]
    rating_count = fields["rating_count"]
    assert rating_count == {"type": "number"}
