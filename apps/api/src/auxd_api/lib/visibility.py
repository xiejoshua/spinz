"""Single source of truth for ``can_read`` content-access decisions.

This module implements the auxd visibility matrix (plan §3.3, §6) as a pure,
side-effect-free policy layer. It deliberately knows nothing about Beanie,
MongoDB, or the concrete shape of any model — callers pass in:

* a :class:`Viewer` (or ``None`` for an anonymous request),
* an :class:`OwnedContent` carrying the owner id, visibility, and soft-delete
  state, and
* a ``relation_resolver`` async callable that the lib invokes **only when
  necessary** to discover the follow / block relationship between the viewer
  and the content's owner.

The matrix collapses three orthogonal axes into a small set of deterministic
rules:

============   ===========  ============================================  ======
Content state  Visibility   Viewer relation                               Result
============   ===========  ============================================  ======
deleted        any          OWNER                                         True
deleted        any          not OWNER                                     False
active         any          BLOCKED                                       False
active         any          BLOCKER                                       False
active         PUBLIC       OWNER / FOLLOWER / NOT_FOLLOWER / ANONYMOUS   True
active         FOLLOWERS    OWNER / FOLLOWER                              True
active         FOLLOWERS    NOT_FOLLOWER / ANONYMOUS                      False
active         PRIVATE      OWNER                                         True
active         PRIVATE      FOLLOWER / NOT_FOLLOWER / ANONYMOUS           False
============   ===========  ============================================  ======

Block symmetry is intentional: a viewer who has blocked the owner does not see
the owner's content either. This matches the product spec's "mutual hide" rule
and prevents stale impressions of someone the viewer has chosen to exclude.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class Visibility(StrEnum):
    """Content visibility level chosen by the owner."""

    PUBLIC = "public"
    FOLLOWERS = "followers"
    PRIVATE = "private"


class ViewerRelation(StrEnum):
    """Computed relationship between a viewer and a content owner.

    Resolved by the caller (typically with a single Mongo aggregation that
    checks both directions of the follow / block edges) and handed to this
    library so the policy decision can stay synchronous and pure.
    """

    ANONYMOUS = "anonymous"
    """No logged-in viewer."""

    OWNER = "owner"
    """Viewer IS the content owner."""

    FOLLOWER = "follower"
    """Viewer follows the owner (mutual follow not required)."""

    NOT_FOLLOWER = "not_follower"
    """Logged-in viewer who does not follow the owner."""

    BLOCKED = "blocked"
    """Owner has blocked the viewer — content always hidden from viewer."""

    BLOCKER = "blocker"
    """Viewer has blocked the owner — content always hidden from viewer (mutual hide)."""


class Viewer(Protocol):
    """Minimal interface for an authenticated viewer.

    Only the stable string ``id`` is required; this lets the policy run against
    Beanie documents, dataclasses, and ad-hoc test doubles interchangeably.
    """

    id: str


class OwnedContent(Protocol):
    """Minimal interface for any content with an owner, visibility, and soft-delete.

    Every readable resource in auxd (posts, comments, profiles) exposes these
    three fields; the policy is the same for all of them.
    """

    owner_id: str
    visibility: Visibility
    deleted_at: datetime | None


RelationResolver = Callable[[Viewer, str], Awaitable[ViewerRelation]]
"""Async callable resolving the viewer's relation to an owner id."""


def can_read_with_relation(
    viewer: Viewer | None,
    content: OwnedContent,
    relation: ViewerRelation,
) -> bool:
    """Return whether ``viewer`` may read ``content`` given a pre-computed relation.

    This is the matrix decision laid bare — no I/O, no awaits. Callers that
    have already loaded follow / block state (e.g., a feed query that batch-
    resolved relations for every item) should use this and skip the resolver.

    Args:
        viewer: Authenticated viewer, or ``None`` for anonymous.
        content: The content being accessed.
        relation: Pre-computed viewer-to-owner relationship.

    Returns:
        ``True`` iff the viewer is permitted to read this content.
    """
    # Soft-deleted content is visible only to its owner (recovery window).
    if content.deleted_at is not None:
        return relation is ViewerRelation.OWNER

    # Anonymous viewers must report ANONYMOUS; a None viewer with any other
    # relation is a programming error caught here defensively.
    if viewer is None and relation is not ViewerRelation.ANONYMOUS:
        return False

    # Block symmetry: hide content from blocked viewers AND from viewers who
    # have blocked the owner.
    if relation in (ViewerRelation.BLOCKED, ViewerRelation.BLOCKER):
        return False

    if content.visibility is Visibility.PUBLIC:
        return True

    if content.visibility is Visibility.FOLLOWERS:
        return relation in (ViewerRelation.OWNER, ViewerRelation.FOLLOWER)

    # PRIVATE: owner only.
    return relation is ViewerRelation.OWNER


async def can_read(
    viewer: Viewer | None,
    content: OwnedContent,
    *,
    relation_resolver: RelationResolver | None = None,
) -> bool:
    """Return whether ``viewer`` may read ``content``, resolving relation on demand.

    The relation resolver is invoked **only** when the answer truly depends on
    the follow / block relationship:

    * Soft-deleted content short-circuits on ownership (owner-id compare).
    * Public, active content short-circuits to ``True`` for everyone.
    * Anonymous viewers short-circuit with ``ViewerRelation.ANONYMOUS``.

    For followers-only / private content with a logged-in non-owner viewer,
    the resolver IS called. If no resolver is supplied in that case, the
    function conservatively returns ``False`` rather than raising — this keeps
    misuse from leaking content, but tests should always pass a resolver when
    they expect a non-trivial path.

    Args:
        viewer: Authenticated viewer, or ``None`` for anonymous requests.
        content: The content being accessed.
        relation_resolver: Async callable ``(viewer, owner_id) -> ViewerRelation``.
            Optional for cases the policy can answer without it.

    Returns:
        ``True`` iff the viewer is permitted to read this content.
    """
    if viewer is None:
        return can_read_with_relation(None, content, ViewerRelation.ANONYMOUS)

    # Owner short-circuit avoids any resolver call when the viewer simply
    # is the owner — common case for "my drafts" / "my deleted post" views.
    if viewer.id == content.owner_id:
        return can_read_with_relation(viewer, content, ViewerRelation.OWNER)

    # Active public content is readable by any non-blocked viewer. But we
    # still must consult the resolver to honour mutual blocks. However, for
    # anonymous viewers we already returned above, and for logged-in viewers
    # the resolver tells us whether blocks apply.
    if content.deleted_at is None and content.visibility is Visibility.PUBLIC:
        if relation_resolver is None:
            # No resolver means we cannot detect a block; in the absence of
            # the resolver, the safe assumption for *public* content is that
            # there's no block to honour (callers without a resolver are
            # asking the simple "is this publicly readable" question).
            return True
        relation = await relation_resolver(viewer, content.owner_id)
        return can_read_with_relation(viewer, content, relation)

    # Anything else (followers-only, private, or any deleted non-owner case)
    # genuinely needs the relation to decide.
    if relation_resolver is None:
        # Conservative default: without a way to verify follow / block state,
        # do not grant access to non-public content.
        return False

    relation = await relation_resolver(viewer, content.owner_id)
    return can_read_with_relation(viewer, content, relation)


__all__ = [
    "OwnedContent",
    "RelationResolver",
    "Viewer",
    "ViewerRelation",
    "Visibility",
    "can_read",
    "can_read_with_relation",
]
