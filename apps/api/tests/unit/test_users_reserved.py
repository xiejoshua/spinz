"""Unit tests for :mod:`auxd_api.modules.users.reserved`."""

from __future__ import annotations

from pathlib import Path

from auxd_api.modules.users.reserved import (
    is_reserved_handle,
    load_reserved_handles,
)


def test_seeded_handles_loaded() -> None:
    """The bundled seed file is loaded and contains a few well-known squats."""
    handles = load_reserved_handles()
    # Three handles guaranteed to be in the seed (per the reserved
    # handles file at apps/api/migrations/seed-data/reserved_handles.txt).
    assert "admin" in handles
    assert "api" in handles
    assert "help" in handles


def test_is_reserved_handle_is_case_insensitive() -> None:
    assert is_reserved_handle("ADMIN") is True
    assert is_reserved_handle("notarealhandlexyz") is False


def test_missing_file_returns_empty_set(tmp_path: Path) -> None:
    """A missing seed file logs a warning and returns an empty frozenset."""
    missing = tmp_path / "missing.txt"
    result = load_reserved_handles(missing)
    assert result == frozenset()


def test_empty_file_returns_empty_set(tmp_path: Path) -> None:
    """An empty/comment-only file resolves to an empty set."""
    empty = tmp_path / "comments_only.txt"
    empty.write_text("# only a comment\n\n# another\n", encoding="utf-8")
    result = load_reserved_handles(empty)
    assert result == frozenset()


def test_custom_seed_file_parses_lowercased(tmp_path: Path) -> None:
    """Whitespace + casing is normalised on load."""
    seed = tmp_path / "mini.txt"
    seed.write_text("# hi\nFoo\n  bar  \nBAZ\n", encoding="utf-8")
    result = load_reserved_handles(seed)
    assert result == frozenset({"foo", "bar", "baz"})
