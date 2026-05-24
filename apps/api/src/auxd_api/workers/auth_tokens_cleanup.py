"""Auth-token cleanup worker (feature 002-auth-email-flows).

Daily arq cron at 04:00 UTC that sweeps both auth-token collections
(:class:`EmailVerificationToken` and :class:`PasswordResetToken`) and
deletes rows whose retention window has elapsed.

Retention contract (FR-105 + plan §6):

* A consumed token (``used_at is not None``) is retained for 7 days
  post-consume so the audit log + analytics funnel can still reference
  it.
* An unconsumed token (``used_at is None``) is retained for 7 days
  post-expiry so the same audit/analytics references still resolve
  even when the token was never clicked.

The 7-day retention mirrors the existing :class:`FailedEmail` cleanup
cadence and is short enough that the collections never grow unbounded
while long enough that ops debugging a 24-hour incident still has the
rows available.

Audit log
=========
Emits exactly one structured ``auth.token_cleanup`` ``log_call`` per
run summarising row counts per collection. No PostHog event — this is
a backend hygiene job, not a user-facing signal.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from auxd_api.lib.observability import log_call
from auxd_api.modules.auth.tokens_models import (
    EmailVerificationToken,
    PasswordResetToken,
)

_LOGGER = logging.getLogger("auxd.worker.auth_tokens_cleanup")

# Retention windows expressed as deltas from "now". A row qualifies for
# deletion when (used_at, if set, OR expires_at, otherwise) precedes
# the cutoff.
_RETENTION_DAYS: Final[int] = 7


async def _sweep_collection(
    document_cls: type[EmailVerificationToken] | type[PasswordResetToken],
    *,
    now: datetime,
) -> int:
    """Delete retention-elapsed rows from ``document_cls`` and return the count.

    Filter matches plan §6: either the row was consumed >=7d ago OR
    the row was never consumed and its ``expires_at`` is >=7d in the
    past. Atomic ``delete_many`` so partial failures don't leave the
    collection in a half-swept state.
    """
    cutoff = now - timedelta(days=_RETENTION_DAYS)
    motor_collection = document_cls.get_motor_collection()
    result = await motor_collection.delete_many(
        {
            "$or": [
                {"used_at": {"$ne": None, "$lt": cutoff}},
                {"used_at": None, "expires_at": {"$lt": cutoff}},
            ]
        }
    )
    deleted: int = int(result.deleted_count or 0)
    return deleted


async def cleanup_auth_tokens(ctx: dict[str, Any]) -> dict[str, int]:
    """arq job entry point — sweep both auth-token collections.

    Returns a small summary dict ``{"verification_deleted": N,
    "reset_deleted": N}`` so the arq result store surfaces a useful
    value for tests + ops debugging.
    """
    now = datetime.now(UTC)
    verification_deleted = await _sweep_collection(EmailVerificationToken, now=now)
    reset_deleted = await _sweep_collection(PasswordResetToken, now=now)

    log_call(
        provider="auxd",
        endpoint="auth.token_cleanup",
        latency_ms=0.0,
        status="ok",
        extra={
            "verification_deleted": verification_deleted,
            "reset_deleted": reset_deleted,
            "job_id": ctx.get("job_id", "manual"),
        },
    )
    _LOGGER.info(
        "auth.token_cleanup",
        extra={
            "event": "auth.token_cleanup",
            "verification_deleted": verification_deleted,
            "reset_deleted": reset_deleted,
        },
    )
    return {
        "verification_deleted": verification_deleted,
        "reset_deleted": reset_deleted,
    }


__all__ = ["cleanup_auth_tokens"]
