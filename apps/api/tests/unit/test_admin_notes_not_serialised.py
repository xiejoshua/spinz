"""Regression guard: every public user serializer must drop admin fields (T158).

The ``User.admin_notes`` / ``User.flagged_for_review`` /
``User.flagged_for_review_at`` fields are internal moderation surfaces
read via Mongo Compass and the founder's ops console. They must NEVER
appear on a public API response. This test parametrises across every
public user-card serializer in the codebase to enforce that contract.

If you add a new public serializer that emits a User payload, register
it in ``_PUBLIC_USER_SERIALIZERS`` below — the parametrised test will
guard it against admin-field leakage.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from auxd_api.modules.auth.routes import _public_user_payload as auth_public_payload
from auxd_api.modules.feed.service import _serialize_user_card as feed_user_card
from auxd_api.modules.reviews.routes import _serialize_user_card as reviews_user_card
from auxd_api.modules.users.models import User
from auxd_api.modules.users.routes import _serialize_user_card as users_user_card

# Sensitive fields that MUST be absent from any public payload.
_ADMIN_FIELDS = frozenset(
    {
        "admin_notes",
        "flagged_for_review",
        "flagged_for_review_at",
        # password_hash + session_version are also internal; cover them
        # opportunistically in the same regression guard.
        "password_hash",
        "session_version",
    }
)


def _make_user_with_admin_data() -> User:
    """Build a User whose admin/sensitive fields are populated.

    All non-default values so a serializer that accidentally copies the
    field would surface a non-empty leaked value the assertion can
    catch.
    """
    return User(
        id="user-admin-data",
        handle="hidden",
        email="hidden@example.com",
        password_hash="$argon2id$test-hash",
        display_name="Hidden",
        admin_notes="this should never leak",
        flagged_for_review=True,
        session_version=99,
    )


# Each serializer is a (name, fn) pair. The ``fn`` is wrapped so all
# signatures degrade to a single positional ``User`` argument — the
# parametrised test doesn't care about the per-serializer keyword
# surface, only the output payload shape.
_PUBLIC_USER_SERIALIZERS: list[tuple[str, Callable[[User], dict[str, Any]]]] = [
    ("auth._public_user_payload", auth_public_payload),
    ("users._serialize_user_card", users_user_card),
    ("reviews._serialize_user_card", reviews_user_card),
    ("feed._serialize_user_card", feed_user_card),
]


@pytest.mark.parametrize(("name", "serializer"), _PUBLIC_USER_SERIALIZERS)
def test_public_user_serializers_drop_admin_fields(
    name: str, serializer: Callable[[User], dict[str, Any]]
) -> None:
    user = _make_user_with_admin_data()
    payload = serializer(user)
    leaked = sorted(_ADMIN_FIELDS & set(payload.keys()))
    assert not leaked, f"{name} leaks admin field(s): {leaked}"
