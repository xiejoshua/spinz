"""MongoDB connection + Beanie init lifecycle (T012).

Owns the process-wide Motor client and the one-shot ``init_beanie()`` call
made at app startup. Constitution P5 (fail-loud): connection failures
propagate out of :func:`init_db` so the container crashes immediately
rather than coming up "healthy" with a broken database.

The canonical list of Beanie Documents managed by auxd lives here as
:data:`ALL_DOCUMENT_MODELS`. Both the runtime app (:mod:`auxd_api.main`)
and the test suite (``tests/conftest.py``) read from this same list so
new Documents need only be registered in one place.
"""

from __future__ import annotations

from typing import Final

from beanie import Document, init_beanie
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConfigurationError, PyMongoError
from pymongo.uri_parser import parse_uri

from auxd_api.modules.albums.models import Album
from auxd_api.modules.backlog.models import Backlog, BacklogItem
from auxd_api.modules.diary.models import DiaryEntry
from auxd_api.modules.gdpr.models import GdprAuditLog
from auxd_api.modules.moderation.models import Report
from auxd_api.modules.notifications.models import FailedEmail, Notification
from auxd_api.modules.notifications.push_models import PushSubscription

# JustFinishedPrompt deferred to v2 per CR-001; class kept importable for forward compat.
from auxd_api.modules.prompts.models import JustFinishedPrompt  # noqa: F401
from auxd_api.modules.reviews.models import Review, ReviewEditHistory, ReviewLike
from auxd_api.modules.seeding.models import CriticSeed, SuggestedFollow
from auxd_api.modules.social.models import Block, Follow, FollowRequest
from auxd_api.modules.social.suggestions_models import Suggestion, SuggestionDismissal
from auxd_api.modules.users.models import HandleRedirect, User

ALL_DOCUMENT_MODELS: list[type[Document]] = [
    # users
    User,
    HandleRedirect,
    # albums
    Album,
    # diary + reviews
    DiaryEntry,
    Review,
    ReviewLike,
    ReviewEditHistory,
    # backlog
    Backlog,
    BacklogItem,
    # social
    Follow,
    FollowRequest,
    Block,
    # social — T104 suggestions (precomputed + dismissals)
    Suggestion,
    SuggestionDismissal,
    # moderation + notifications
    Report,
    Notification,
    FailedEmail,
    PushSubscription,
    # GDPR
    GdprAuditLog,
    # prompts + seeding
    # CR-001: JustFinishedPrompt deferred to v2 — class kept importable
    # (see import above) but not registered with Beanie at MVP.
    SuggestedFollow,
    CriticSeed,
]


_client: AsyncIOMotorClient[dict[str, object]] | None = None

OK: Final[str] = "ok"
DOWN: Final[str] = "down"


def _redact_uri(uri: str) -> str:
    """Return ``uri`` with any inline password replaced by ``***``.

    Best-effort: ``mongodb://user:pass@host/db`` becomes
    ``mongodb://user:***@host/db``. URIs without credentials pass through
    unchanged. Used in error messages so a misconfigured operator can see
    *which* URI failed without leaking the secret to logs.
    """
    try:
        parsed = parse_uri(uri)
    except Exception:
        return "<unparseable URI>"
    password = parsed.get("password")
    if not password:
        return uri
    return uri.replace(f":{password}@", ":***@", 1)


def _database_name_from_uri(uri: str) -> str:
    """Extract the database name from ``uri`` or raise ``RuntimeError``.

    A bare ``mongodb://host:27017`` URI parses fine but carries no default
    database — Beanie requires one, so reject the URI loudly before any
    network I/O.
    """
    try:
        parsed = parse_uri(uri)
    except Exception as exc:
        raise RuntimeError(f"MONGODB_URI is malformed (got: {_redact_uri(uri)}): {exc}") from exc
    database = parsed.get("database")
    if not database:
        raise RuntimeError(f"MONGODB_URI must include a database name (got: {_redact_uri(uri)})")
    return str(database)


async def init_db(mongodb_uri: str) -> None:
    """Connect to MongoDB and register every Beanie Document.

    Steps:
        1. Parse the database name out of ``mongodb_uri`` (raise if absent).
        2. Open a Motor client and ping ``admin`` to verify the connection
           is actually reachable — Motor's constructor is lazy, so without
           an explicit ping a wrong host would not surface until the first
           query.
        3. Hand the resulting database to :func:`beanie.init_beanie` with
           :data:`ALL_DOCUMENT_MODELS`.
        4. Stash the client at module scope for :func:`close_db`.

    Any failure propagates (Constitution P5).
    """
    global _client

    database_name = _database_name_from_uri(mongodb_uri)
    client: AsyncIOMotorClient[dict[str, object]] = AsyncIOMotorClient(mongodb_uri)

    try:
        await client.admin.command("ping")
    except Exception:
        client.close()
        raise

    database: AsyncIOMotorDatabase[dict[str, object]] = client[database_name]
    await init_beanie(database=database, document_models=list(ALL_DOCUMENT_MODELS))
    _client = client


async def close_db() -> None:
    """Dispose of the Motor client, if any. Idempotent."""
    global _client
    if _client is not None:
        _client.close()
        _client = None


def get_client() -> AsyncIOMotorClient[dict[str, object]]:
    """Return the singleton Motor client, raising if :func:`init_db` has not run."""
    if _client is None:
        raise RuntimeError("MongoDB client is not initialised; call init_db() first.")
    return _client


def get_database(mongodb_uri: str) -> AsyncIOMotorDatabase[dict[str, object]]:
    """Return the active Motor database handle, parsing its name from ``mongodb_uri``.

    Convenience for callers (the migration runner, ad-hoc admin
    scripts) that need a database handle without re-creating one of
    their own. Raises ``RuntimeError`` when :func:`init_db` has not
    yet been called, mirroring :func:`get_client`.
    """
    database_name = _database_name_from_uri(mongodb_uri)
    return get_client()[database_name]


async def ping_db() -> str:
    """Return :data:`OK` if MongoDB is reachable, :data:`DOWN` otherwise.

    Suitable for ``/healthz`` sub-checks: never raises. Returns
    :data:`DOWN` when :func:`init_db` has not run (e.g. unit tests
    constructed via a bare :class:`TestClient` without lifespan) or when
    the admin ``ping`` fails for any reason.
    """
    if _client is None:
        return DOWN
    try:
        await _client.admin.command("ping")
    except PyMongoError:
        return DOWN
    return OK


# Re-export ``ConfigurationError`` so callers wanting to handle URI-related
# misconfiguration can do so without importing from pymongo directly.
__all__ = [
    "ALL_DOCUMENT_MODELS",
    "DOWN",
    "ConfigurationError",
    "OK",
    "close_db",
    "get_client",
    "get_database",
    "init_db",
    "ping_db",
]
