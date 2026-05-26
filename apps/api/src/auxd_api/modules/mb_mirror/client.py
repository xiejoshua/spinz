"""Async libSQL client for Turso, built on httpx.

Avoids pinning to ``libsql-experimental`` or ``libsql-client`` —
both are in flux as of 2026 and changes break our async story.
The HTTP pipeline API (``/v2/pipeline``) is documented and stable;
a thin httpx wrapper is ~150 lines and gives us full control over
batching, timeouts, and error handling.

Protocol reference
==================
https://docs.turso.tech/sdk/http/reference

Each request to ``POST /v2/pipeline`` carries a JSON body with a
list of ``requests`` (statements). The server returns a parallel
list of ``results`` (rows + columns) or ``errors``. Statements
within a single pipeline run atomically — useful for the ETL's
batch upserts where partial application would corrupt the mirror.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import httpx

_LOGGER = logging.getLogger("auxd.mb_mirror.client")


@dataclass(slots=True)
class StatementResult:
    """One pipeline-request's result row set.

    ``columns`` is the column-name list as the server reported it;
    ``rows`` is a list-of-lists of cell values matched against the
    column order. Cells are already typed (Turso returns ints,
    strings, floats, nulls) so callers don't have to parse.
    """

    columns: list[str]
    rows: list[list[Any]]

    def dicts(self) -> list[dict[str, Any]]:
        """Project rows into dicts keyed by column name."""
        return [dict(zip(self.columns, row, strict=False)) for row in self.rows]


class TursoClient:
    """Async client for one Turso database.

    Construct from ``TURSO_DATABASE_URL`` + ``TURSO_AUTH_TOKEN``
    (see :mod:`auxd_api.settings`). Use as an async context
    manager to ensure the underlying httpx client closes cleanly.

    .. code-block:: python

        async with TursoClient.from_settings(settings) as client:
            result = await client.execute(
                "SELECT mbid, title FROM albums_mirror WHERE mbid = ?",
                params=[some_mbid],
            )
            for row in result.dicts():
                print(row)
    """

    def __init__(self, *, http_url: str, auth_token: str, timeout: float = 90.0) -> None:
        # 90s default covers bulk-upsert pipelines on Turso free tier
        # where a single multi-row INSERT can take 10-60s when the
        # FTS5 sync triggers fire across hundreds of rows. Read paths
        # complete in <100ms so the higher ceiling never bites them.
        self._http_url = http_url.rstrip("/")
        self._auth_token = auth_token
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @classmethod
    def from_settings(cls, settings: Any) -> TursoClient | None:
        """Build a client from the API settings, or ``None`` if disabled.

        The mirror is gated on ``TURSO_DATABASE_URL`` being set — when
        it isn't, callers get ``None`` and should treat that as "mirror
        unavailable, fall through to the existing search tiers."
        """
        url = getattr(settings, "TURSO_DATABASE_URL", None)
        token = getattr(settings, "TURSO_AUTH_TOKEN", None)
        if not url or not token:
            return None
        return cls(http_url=_normalize_url(url), auth_token=token)

    async def __aenter__(self) -> TursoClient:
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self._auth_token}"},
            timeout=self._timeout,
        )
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying httpx client. Idempotent."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Query surface
    # ------------------------------------------------------------------

    async def execute(  # noqa: ASYNC109 — ``timeout`` here is passed to httpx, not asyncio
        self,
        sql: str,
        *,
        params: list[Any] | None = None,
        timeout: float | None = None,  # noqa: ASYNC109 — httpx timeout, not asyncio deadline
    ) -> StatementResult:
        """Run one statement and return its result set.

        For positional ``?`` placeholders pass ``params`` as a list;
        for named ``:name`` placeholders, pass a dict via
        :meth:`execute_named`.

        ``timeout`` overrides the client's default for this call only.
        Use it for genuinely-long statements (the FTS5 rebuild scans
        every row in ``albums_mirror`` and can run several minutes on
        a populated mirror) without re-creating the client.
        """
        return (await self.execute_batch([(sql, params or [])], timeout=timeout))[0]

    async def execute_named(
        self,
        sql: str,
        *,
        params: dict[str, Any],
    ) -> StatementResult:
        """Run one statement with named parameters."""
        request = _build_named_request(sql, params)
        results = await self._pipeline([request])
        return results[0]

    async def execute_batch(  # noqa: ASYNC109 — httpx timeout, not asyncio deadline
        self,
        statements: Iterable[tuple[str, list[Any]]],
        *,
        timeout: float | None = None,  # noqa: ASYNC109 — httpx timeout, not asyncio deadline
    ) -> list[StatementResult]:
        """Run many statements atomically in one HTTP round-trip.

        Used by the ETL's bulk-upsert path — sending 500 INSERTs in
        one pipeline call is dramatically faster than 500 round trips
        + lets Turso batch the underlying SQLite WAL writes.

        ``timeout`` overrides the client default for this single
        call. Necessary for long ops like the FTS5 rebuild after
        bulk load.
        """
        requests = [_build_positional_request(sql, params) for sql, params in statements]
        return await self._pipeline(requests, timeout=timeout)

    # ------------------------------------------------------------------
    # Pipeline transport
    # ------------------------------------------------------------------

    async def _pipeline(  # noqa: ASYNC109 — httpx timeout, not asyncio deadline
        self,
        requests: list[dict[str, Any]],
        *,
        timeout: float | None = None,  # noqa: ASYNC109 — httpx timeout, not asyncio deadline
    ) -> list[StatementResult]:
        if self._client is None:
            raise RuntimeError(
                "TursoClient used outside `async with` — wrap calls in the context manager."
            )

        body = {
            "requests": [
                *requests,
                {"type": "close"},  # close the implicit transaction stream
            ]
        }
        post_kwargs: dict[str, Any] = {"json": body}
        if timeout is not None:
            post_kwargs["timeout"] = timeout
        response = await self._client.post(f"{self._http_url}/v2/pipeline", **post_kwargs)
        response.raise_for_status()
        payload = response.json()

        results: list[StatementResult] = []
        for entry in payload.get("results", []):
            kind = entry.get("type")
            if kind == "error":
                err = entry.get("error", {})
                raise TursoExecutionError(
                    f"libSQL error: {err.get('message', 'unknown')} (code={err.get('code')})"
                )
            if kind != "ok":
                # Skip the close-marker echo and any other
                # non-statement responses Turso emits.
                continue
            inner = entry.get("response", {})
            if inner.get("type") != "execute":
                continue
            result = inner.get("result", {})
            cols = [c["name"] for c in result.get("cols", [])]
            rows = [[_unwrap_cell(cell) for cell in row] for row in result.get("rows", [])]
            results.append(StatementResult(columns=cols, rows=rows))
        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TursoExecutionError(RuntimeError):
    """libSQL returned a SQL-layer error.

    Distinct from network/HTTP errors (which propagate as the usual
    httpx exceptions) so callers can branch on "the database said
    no" vs "the network ate the request."
    """


def _normalize_url(raw: str) -> str:
    """Accept both ``libsql://...`` and ``https://...`` forms.

    Turso surface both protocols against the same backend. The HTTP
    pipeline lives at ``https://``; we just swap the scheme when the
    user provides the libsql:// form so they can paste whichever the
    Turso CLI gave them.
    """
    if raw.startswith("libsql://"):
        return "https://" + raw[len("libsql://") :]
    return raw


def _build_positional_request(sql: str, params: list[Any]) -> dict[str, Any]:
    return {
        "type": "execute",
        "stmt": {
            "sql": sql,
            "args": [_wrap_cell(value) for value in params],
        },
    }


def _build_named_request(sql: str, params: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "execute",
        "stmt": {
            "sql": sql,
            "named_args": [
                {"name": key, "value": _wrap_cell(value)} for key, value in params.items()
            ],
        },
    }


def _wrap_cell(value: Any) -> dict[str, Any]:
    """Convert a Python value to Turso's typed-cell wire format."""
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        # bool is a subclass of int — branch first.
        return {"type": "integer", "value": "1" if value else "0"}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float", "value": value}
    if isinstance(value, bytes):
        import base64

        return {"type": "blob", "base64": base64.b64encode(value).decode("ascii")}
    return {"type": "text", "value": str(value)}


def _unwrap_cell(cell: dict[str, Any]) -> Any:
    """Decode a Turso typed-cell into a Python value."""
    kind = cell.get("type")
    if kind == "null":
        return None
    if kind == "integer":
        return int(cell["value"])
    if kind == "float":
        return float(cell["value"])
    if kind == "blob":
        import base64

        return base64.b64decode(cell["base64"])
    return cell.get("value")


__all__ = ["StatementResult", "TursoClient", "TursoExecutionError"]
