"""Unit tests for :mod:`auxd_api.lib.visibility`.

Strategy:

* A hypothesis-driven property test sweeps the full ``Visibility`` ×
  ``ViewerRelation`` × deleted-flag matrix and compares the implementation
  against an in-test reference table — guarantees every cell is exercised
  and that the live function and the reference cannot drift without the
  test catching it.
* Explicit unit tests pin the high-value branches (anonymous, owner-only,
  block symmetry, deleted-only-to-owner) so a regression produces a
  pinpoint failure rather than only the property test going red.
* Resolver-behaviour tests assert that ``can_read`` calls the resolver
  exactly when and only when it must — preventing accidental DB hits in
  the public / anonymous fast paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from auxd_api.lib.visibility import (
    OwnedContent,
    Viewer,
    ViewerRelation,
    Visibility,
    can_read,
    can_read_with_relation,
)

# --------------------------------------------------------------------------- #
# Test doubles
# --------------------------------------------------------------------------- #


@dataclass
class FakeViewer:
    """Test double satisfying the :class:`Viewer` protocol."""

    id: str


@dataclass
class FakeContent:
    """Test double satisfying the :class:`OwnedContent` protocol."""

    owner_id: str
    visibility: Visibility
    deleted_at: datetime | None = None


# Sanity check: the test doubles really do satisfy the runtime-untyped Protocols.
_v: Viewer = FakeViewer(id="u_viewer")
_c: OwnedContent = FakeContent(owner_id="u_owner", visibility=Visibility.PUBLIC)


# --------------------------------------------------------------------------- #
# Reference matrix — the spec, rendered as data.
# --------------------------------------------------------------------------- #


def _expected(visibility: Visibility, relation: ViewerRelation, deleted: bool) -> bool:
    """Compute the spec-correct expected value for one matrix cell.

    Mirrors the table in ``visibility.py``'s module docstring. Implemented
    independently of the production code so the property test catches any
    drift between the two.
    """
    if deleted:
        return relation is ViewerRelation.OWNER
    if relation in (ViewerRelation.BLOCKED, ViewerRelation.BLOCKER):
        return False
    if visibility is Visibility.PUBLIC:
        return True
    if visibility is Visibility.FOLLOWERS:
        return relation in (ViewerRelation.OWNER, ViewerRelation.FOLLOWER)
    # PRIVATE
    return relation is ViewerRelation.OWNER


# --------------------------------------------------------------------------- #
# Property-based: the full 3 × 6 × 2 = 36-cell matrix.
# --------------------------------------------------------------------------- #


@given(
    visibility=st.sampled_from(list(Visibility)),
    relation=st.sampled_from(list(ViewerRelation)),
    deleted=st.booleans(),
)
def test_matrix_matches_reference(
    visibility: Visibility,
    relation: ViewerRelation,
    deleted: bool,
) -> None:
    """Every cell of the matrix matches the in-test reference table."""
    viewer: Viewer | None = (
        None if relation is ViewerRelation.ANONYMOUS else FakeViewer(id="u_viewer")
    )
    content = FakeContent(
        owner_id="u_viewer" if relation is ViewerRelation.OWNER else "u_owner",
        visibility=visibility,
        deleted_at=datetime(2026, 1, 1, tzinfo=UTC) if deleted else None,
    )
    assert can_read_with_relation(viewer, content, relation) is _expected(
        visibility, relation, deleted
    )


def test_matrix_covers_every_cell_explicitly() -> None:
    """Belt-and-suspenders: enumerate all 36 cells and assert each one."""
    seen: set[tuple[Visibility, ViewerRelation, bool]] = set()
    for visibility in Visibility:
        for relation in ViewerRelation:
            for deleted in (False, True):
                viewer: Viewer | None = (
                    None if relation is ViewerRelation.ANONYMOUS else FakeViewer(id="u_viewer")
                )
                content = FakeContent(
                    owner_id="u_viewer" if relation is ViewerRelation.OWNER else "u_owner",
                    visibility=visibility,
                    deleted_at=datetime(2026, 1, 1, tzinfo=UTC) if deleted else None,
                )
                assert can_read_with_relation(viewer, content, relation) is _expected(
                    visibility, relation, deleted
                )
                seen.add((visibility, relation, deleted))
    assert len(seen) == 3 * 6 * 2  # 36 cells


# --------------------------------------------------------------------------- #
# Property-based invariants
# --------------------------------------------------------------------------- #


@given(
    visibility=st.sampled_from(list(Visibility)),
    relation=st.sampled_from([ViewerRelation.BLOCKED, ViewerRelation.BLOCKER]),
)
def test_block_symmetry_active_content(visibility: Visibility, relation: ViewerRelation) -> None:
    """BLOCKED and BLOCKER never see active content of any visibility."""
    viewer = FakeViewer(id="u_viewer")
    content = FakeContent(owner_id="u_owner", visibility=visibility, deleted_at=None)
    assert can_read_with_relation(viewer, content, relation) is False


@given(
    visibility=st.sampled_from(list(Visibility)),
    deleted=st.booleans(),
)
def test_owner_always_sees_own_content(visibility: Visibility, deleted: bool) -> None:
    """The owner can always see their own content — active OR soft-deleted."""
    viewer = FakeViewer(id="u_owner")
    content = FakeContent(
        owner_id="u_owner",
        visibility=visibility,
        deleted_at=datetime(2026, 1, 1, tzinfo=UTC) if deleted else None,
    )
    assert can_read_with_relation(viewer, content, ViewerRelation.OWNER) is True


# --------------------------------------------------------------------------- #
# High-value explicit unit tests (one per important branch)
# --------------------------------------------------------------------------- #


def test_public_active_visible_to_anonymous() -> None:
    content = FakeContent(owner_id="u_owner", visibility=Visibility.PUBLIC)
    assert can_read_with_relation(None, content, ViewerRelation.ANONYMOUS) is True


@pytest.mark.parametrize(
    "relation",
    [
        ViewerRelation.OWNER,
        ViewerRelation.FOLLOWER,
        ViewerRelation.NOT_FOLLOWER,
        ViewerRelation.ANONYMOUS,
    ],
)
def test_public_active_visible_to_anyone(relation: ViewerRelation) -> None:
    viewer: Viewer | None = (
        None if relation is ViewerRelation.ANONYMOUS else FakeViewer(id="u_viewer")
    )
    owner_id = "u_viewer" if relation is ViewerRelation.OWNER else "u_owner"
    content = FakeContent(owner_id=owner_id, visibility=Visibility.PUBLIC)
    assert can_read_with_relation(viewer, content, relation) is True


def test_followers_active_visible_to_follower() -> None:
    viewer = FakeViewer(id="u_viewer")
    content = FakeContent(owner_id="u_owner", visibility=Visibility.FOLLOWERS)
    assert can_read_with_relation(viewer, content, ViewerRelation.FOLLOWER) is True


def test_followers_active_hidden_from_not_follower() -> None:
    viewer = FakeViewer(id="u_viewer")
    content = FakeContent(owner_id="u_owner", visibility=Visibility.FOLLOWERS)
    assert can_read_with_relation(viewer, content, ViewerRelation.NOT_FOLLOWER) is False


def test_followers_active_hidden_from_anonymous() -> None:
    content = FakeContent(owner_id="u_owner", visibility=Visibility.FOLLOWERS)
    assert can_read_with_relation(None, content, ViewerRelation.ANONYMOUS) is False


@pytest.mark.parametrize(
    "relation",
    [
        ViewerRelation.FOLLOWER,
        ViewerRelation.NOT_FOLLOWER,
        ViewerRelation.ANONYMOUS,
    ],
)
def test_private_active_visible_only_to_owner(relation: ViewerRelation) -> None:
    viewer: Viewer | None = (
        None if relation is ViewerRelation.ANONYMOUS else FakeViewer(id="u_viewer")
    )
    content = FakeContent(owner_id="u_owner", visibility=Visibility.PRIVATE)
    assert can_read_with_relation(viewer, content, relation) is False


def test_private_active_visible_to_owner() -> None:
    viewer = FakeViewer(id="u_owner")
    content = FakeContent(owner_id="u_owner", visibility=Visibility.PRIVATE)
    assert can_read_with_relation(viewer, content, ViewerRelation.OWNER) is True


@pytest.mark.parametrize("visibility", list(Visibility))
@pytest.mark.parametrize(
    "relation",
    [
        ViewerRelation.FOLLOWER,
        ViewerRelation.NOT_FOLLOWER,
        ViewerRelation.ANONYMOUS,
        ViewerRelation.BLOCKED,
        ViewerRelation.BLOCKER,
    ],
)
def test_deleted_visible_only_to_owner(visibility: Visibility, relation: ViewerRelation) -> None:
    """Soft-deleted content is hidden from everyone except the owner."""
    viewer: Viewer | None = (
        None if relation is ViewerRelation.ANONYMOUS else FakeViewer(id="u_viewer")
    )
    content = FakeContent(
        owner_id="u_owner",
        visibility=visibility,
        deleted_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert can_read_with_relation(viewer, content, relation) is False


@pytest.mark.parametrize("visibility", list(Visibility))
def test_deleted_visible_to_owner(visibility: Visibility) -> None:
    viewer = FakeViewer(id="u_owner")
    content = FakeContent(
        owner_id="u_owner",
        visibility=visibility,
        deleted_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert can_read_with_relation(viewer, content, ViewerRelation.OWNER) is True


@pytest.mark.parametrize("visibility", list(Visibility))
def test_blocked_sees_nothing(visibility: Visibility) -> None:
    viewer = FakeViewer(id="u_viewer")
    content = FakeContent(owner_id="u_owner", visibility=visibility)
    assert can_read_with_relation(viewer, content, ViewerRelation.BLOCKED) is False


@pytest.mark.parametrize("visibility", list(Visibility))
def test_blocker_sees_nothing(visibility: Visibility) -> None:
    """Mutual hide: a viewer who blocked the owner doesn't see their content either."""
    viewer = FakeViewer(id="u_viewer")
    content = FakeContent(owner_id="u_owner", visibility=visibility)
    assert can_read_with_relation(viewer, content, ViewerRelation.BLOCKER) is False


def test_none_viewer_with_non_anonymous_relation_returns_false() -> None:
    """Defensive: ``None`` viewer combined with a non-anon relation must not leak."""
    content = FakeContent(owner_id="u_owner", visibility=Visibility.PUBLIC)
    # Caller mis-specified — the policy must err on the side of safety.
    assert can_read_with_relation(None, content, ViewerRelation.OWNER) is False


# --------------------------------------------------------------------------- #
# Async wrapper: resolver invocation semantics
# --------------------------------------------------------------------------- #


class CountingResolver:
    """Tracks how many times ``can_read`` consulted the resolver."""

    def __init__(self, relation: ViewerRelation) -> None:
        self._relation = relation
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, viewer: Viewer, owner_id: str) -> ViewerRelation:
        self.calls.append((viewer.id, owner_id))
        return self._relation


async def test_can_read_with_relation_is_sync_and_skips_resolver() -> None:
    """``can_read_with_relation`` is a pure function — no resolver, no awaits."""
    viewer = FakeViewer(id="u_viewer")
    content = FakeContent(owner_id="u_owner", visibility=Visibility.FOLLOWERS)
    # No resolver in scope at all — purely sync call.
    result = can_read_with_relation(viewer, content, ViewerRelation.FOLLOWER)
    assert result is True


async def test_can_read_short_circuits_public_active_without_resolver() -> None:
    """Public active content returns True even when ``relation_resolver=None``."""
    viewer = FakeViewer(id="u_viewer")
    content = FakeContent(owner_id="u_owner", visibility=Visibility.PUBLIC)
    assert await can_read(viewer, content, relation_resolver=None) is True


async def test_can_read_anonymous_does_not_call_resolver() -> None:
    """Anonymous viewers always work and never invoke the resolver."""
    resolver = CountingResolver(ViewerRelation.FOLLOWER)
    content_public = FakeContent(owner_id="u_owner", visibility=Visibility.PUBLIC)
    content_followers = FakeContent(owner_id="u_owner", visibility=Visibility.FOLLOWERS)

    assert await can_read(None, content_public, relation_resolver=resolver) is True
    assert await can_read(None, content_followers, relation_resolver=resolver) is False
    assert resolver.calls == []  # resolver never invoked for anon viewers


async def test_can_read_owner_short_circuits_resolver() -> None:
    """When ``viewer.id == content.owner_id`` the resolver is not invoked."""
    resolver = CountingResolver(ViewerRelation.NOT_FOLLOWER)
    viewer = FakeViewer(id="u_owner")
    content = FakeContent(owner_id="u_owner", visibility=Visibility.PRIVATE)
    assert await can_read(viewer, content, relation_resolver=resolver) is True
    assert resolver.calls == []


async def test_can_read_resolves_for_followers_visibility() -> None:
    """FOLLOWERS visibility with a non-owner viewer triggers the resolver."""
    resolver = CountingResolver(ViewerRelation.FOLLOWER)
    viewer = FakeViewer(id="u_viewer")
    content = FakeContent(owner_id="u_owner", visibility=Visibility.FOLLOWERS)
    assert await can_read(viewer, content, relation_resolver=resolver) is True
    assert resolver.calls == [("u_viewer", "u_owner")]


async def test_can_read_resolves_for_private_visibility() -> None:
    """PRIVATE visibility with a non-owner viewer triggers the resolver."""
    resolver = CountingResolver(ViewerRelation.NOT_FOLLOWER)
    viewer = FakeViewer(id="u_viewer")
    content = FakeContent(owner_id="u_owner", visibility=Visibility.PRIVATE)
    assert await can_read(viewer, content, relation_resolver=resolver) is False
    assert resolver.calls == [("u_viewer", "u_owner")]


async def test_can_read_public_consults_resolver_for_blocks() -> None:
    """Public-content path still honours mutual blocks when a resolver is provided."""
    resolver = CountingResolver(ViewerRelation.BLOCKED)
    viewer = FakeViewer(id="u_viewer")
    content = FakeContent(owner_id="u_owner", visibility=Visibility.PUBLIC)
    assert await can_read(viewer, content, relation_resolver=resolver) is False
    assert resolver.calls == [("u_viewer", "u_owner")]


async def test_can_read_no_resolver_followers_returns_false_conservatively() -> None:
    """Without a resolver, non-public content for a non-owner viewer is denied."""
    viewer = FakeViewer(id="u_viewer")
    content = FakeContent(owner_id="u_owner", visibility=Visibility.FOLLOWERS)
    assert await can_read(viewer, content, relation_resolver=None) is False


async def test_can_read_no_resolver_private_returns_false_conservatively() -> None:
    viewer = FakeViewer(id="u_viewer")
    content = FakeContent(owner_id="u_owner", visibility=Visibility.PRIVATE)
    assert await can_read(viewer, content, relation_resolver=None) is False


async def test_can_read_deleted_visible_to_owner_no_resolver() -> None:
    """Owner can recover their soft-deleted content without any resolver call."""
    resolver = CountingResolver(ViewerRelation.NOT_FOLLOWER)
    viewer = FakeViewer(id="u_owner")
    content = FakeContent(
        owner_id="u_owner",
        visibility=Visibility.PUBLIC,
        deleted_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert await can_read(viewer, content, relation_resolver=resolver) is True
    assert resolver.calls == []


async def test_can_read_deleted_hidden_from_non_owner_no_resolver() -> None:
    """A non-owner viewer is denied a deleted item even if a resolver is provided."""
    resolver = CountingResolver(ViewerRelation.FOLLOWER)
    viewer = FakeViewer(id="u_viewer")
    content = FakeContent(
        owner_id="u_owner",
        visibility=Visibility.PUBLIC,
        deleted_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert await can_read(viewer, content, relation_resolver=resolver) is False


# --------------------------------------------------------------------------- #
# Enum sanity
# --------------------------------------------------------------------------- #


def test_visibility_string_values() -> None:
    assert Visibility.PUBLIC.value == "public"
    assert Visibility.FOLLOWERS.value == "followers"
    assert Visibility.PRIVATE.value == "private"


def test_viewer_relation_string_values() -> None:
    assert ViewerRelation.ANONYMOUS.value == "anonymous"
    assert ViewerRelation.OWNER.value == "owner"
    assert ViewerRelation.FOLLOWER.value == "follower"
    assert ViewerRelation.NOT_FOLLOWER.value == "not_follower"
    assert ViewerRelation.BLOCKED.value == "blocked"
    assert ViewerRelation.BLOCKER.value == "blocker"
