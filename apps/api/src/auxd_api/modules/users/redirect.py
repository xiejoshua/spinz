"""Handle-redirect resolver (T060).

Pure service helper consumed by future profile-page routes (§14). Given a
URL handle, returns the canonical :class:`User` plus the canonical
handle so the route layer can decide between a direct render and a
``301`` redirect to the new handle.

Resolver contract::

    user, canonical = await resolve_handle("oldname")

* ``("oldname")`` matches the current ``User.handle`` → returns the
  user and ``"oldname"`` — no redirect needed.
* ``("oldname")`` matches a :class:`HandleRedirect.old_handle` →
  returns the user that now owns the redirected handle and the
  current ``User.handle`` value (which may differ from the
  ``new_handle`` stored on the redirect if the user has since changed
  it again).
* No match → ``(None, None)``.

The function intentionally does *not* check ``HandleRedirect.created_at``
against the 90-day window from FR-029 — that's a separate sweep job's
responsibility (out of scope for the §5 cluster). At MVP, every
redirect that exists is honoured; the cleanup job purges expired rows.
"""

from __future__ import annotations

from auxd_api.modules.users.models import HandleRedirect, User

__all__ = ["resolve_handle"]


async def resolve_handle(handle: str) -> tuple[User | None, str | None]:
    """Look up ``handle`` against current users + the redirect table.

    Returns:
        ``(user, canonical_handle)`` when a match exists, where
        ``canonical_handle`` is the user's *current* handle (so callers
        can decide whether to issue a 301 by comparing against the input).
        ``(None, None)`` when neither the users nor the redirects table
        has a match.
    """
    if not handle:
        return None, None
    normalised = handle.strip().lower()

    direct = await User.find_one(User.handle == normalised)
    if direct is not None:
        return direct, direct.handle

    redirect = await HandleRedirect.find_one(HandleRedirect.old_handle == normalised)
    if redirect is None:
        return None, None
    user = await User.get(redirect.user_id)
    if user is None:
        # Orphan redirect — the user has been hard-deleted (cascade in
        # T058 should also delete the redirect row, but defence-in-depth
        # against any stragglers): treat as unknown.
        return None, None
    return user, user.handle
