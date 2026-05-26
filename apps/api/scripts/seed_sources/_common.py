"""Shared plumbing for catalog-seed CSV generators.

Scope is intentionally small: an HTTP helper that's polite +
retry-aware, an HTML parse helper that fronts selectolax, a CSV
writer that matches the ingest pipeline's expected schema, and a
:class:`SeedEntry` data shape every scraper outputs.

The user-agent identifies the script honestly so a publisher running
log analysis can attribute the traffic. Rate-limit: 1 req/sec by
default; scrapers that need to crawl paginated indices use
``polite_get`` between hits.
"""

from __future__ import annotations

import csv
import logging
import ssl
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
import truststore
from selectolax.parser import HTMLParser

# Use the OS-native trust store via :mod:`truststore` so HTTPS works
# transparently inside corp TLS-MITM environments (Zscaler, Bluecoat,
# Cisco Umbrella) that inject their own root CA into the macOS
# Keychain / Windows cert manager. Python's bundled certifi list
# doesn't see those roots; this swap is the upstream-recommended
# workaround. Inject early — affects every httpx client built below.
truststore.inject_into_ssl()
_SSL_CONTEXT = ssl.create_default_context()

_LOGGER = logging.getLogger("auxd.seed_sources")

# Identify ourselves honestly — publishers commonly block traffic that
# looks like a bot but pretends to be a browser, and they're more
# tolerant when we say who we are upfront.
USER_AGENT = (
    "auxd-catalog-seeder/0.1 (+https://github.com/auxd/auxd; catalog seed for music diary platform)"
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    # gzip + deflate only — Brotli (br) requires the optional ``brotli``
    # extra on httpx, which we don't pull in. AOTY happily returns
    # brotli-encoded bodies when we advertise ``br`` and the response
    # then decodes to garbage. Sticking to native-supported encodings
    # avoids the foot-gun.
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

# Output directory aligns with the catalog_seed source loader's
# expectations — paths resolve relative to apps/api/data/seed_lists/.
#
# parents[0]=seed_sources/ [1]=scripts/ [2]=api/
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "seed_lists"

_LAST_REQUEST_AT = 0.0
# Per-request floor. AOTY in particular trips its bot gate when hits
# arrive faster than ~2s apart on a fresh client; the default
# generous interval has been worth the few extra seconds across a
# full multi-year scrape.
_MIN_REQUEST_INTERVAL_S = 2.0

# Status codes we treat as "transient — back off and retry". 429
# is the conventional rate-limit signal; some sites (AOTY, Pitchfork)
# also return 403 instead, so we batch them together.
_TRANSIENT_4XX = frozenset({403, 429})


@dataclass(frozen=True, slots=True)
class SeedEntry:
    """One album row in a generated CSV.

    Matches the schema consumed by
    :func:`auxd_api.modules.catalog_seed.sources.load_from_csv`.
    """

    artist: str
    title: str
    year: int | None = None
    source_rank: int | None = None


def polite_get(url: str, *, timeout: float = 20.0, retries: int = 4) -> httpx.Response:
    """GET with a 2 req/sec floor + retry on 5xx / 403 / 429.

    Single-threaded politeness — each call blocks until at least
    ``_MIN_REQUEST_INTERVAL_S`` has elapsed since the previous request
    on this process. Scrapers crawling paginated indices benefit from
    this directly; ad-hoc one-shot fetches pay a negligible delay.

    Retries cover three transient failure modes:

    * Network errors (timeout, reset) — connection-layer hiccups.
    * 5xx — upstream wobble.
    * 403 / 429 — bot-gate trip + classical rate-limit. AOTY in
      particular bounces 403 instead of 429 when the request cadence
      gets aggressive; backing off and retrying clears it without
      needing to spoof a browser User-Agent.

    Backoff is exponential (2s, 4s, 8s, 16s) so the second pass after
    a 403 has time to drop out of the publisher's rolling window.

    On exhausted retries, raises :class:`RuntimeError` (not
    ``HTTPStatusError``) so callers can catch a single error type
    without importing httpx. Permanent 4xx (404, 410, 451) propagate
    as :class:`httpx.HTTPStatusError` — those won't fix themselves.
    """
    global _LAST_REQUEST_AT
    elapsed = time.monotonic() - _LAST_REQUEST_AT
    if elapsed < _MIN_REQUEST_INTERVAL_S:
        time.sleep(_MIN_REQUEST_INTERVAL_S - elapsed)

    last_exc: Exception | None = None
    last_status: int | None = None
    with httpx.Client(
        headers=DEFAULT_HEADERS,
        timeout=timeout,
        follow_redirects=True,
        verify=_SSL_CONTEXT,
    ) as client:
        for attempt in range(retries):
            backoff = 2.0 ** (attempt + 1)  # 2s, 4s, 8s, 16s
            try:
                # Send a credible Referer so bot gates that check it
                # see the request as coming from the site itself.
                # Same-origin Referer is the cheapest tell that we're
                # not a naive curl loop.
                referer = _same_origin_referer(url)
                response = client.get(
                    url,
                    headers={"Referer": referer} if referer else None,
                )
            except httpx.RequestError as exc:
                last_exc = exc
                _LOGGER.warning(
                    "seed_sources.fetch_retry",
                    extra={
                        "event": "seed_sources.fetch_retry",
                        "url": url,
                        "attempt": attempt + 1,
                        "error": repr(exc),
                    },
                )
                time.sleep(backoff)
                continue
            _LAST_REQUEST_AT = time.monotonic()
            last_status = response.status_code
            if response.status_code == 200:
                return response
            if response.status_code in _TRANSIENT_4XX or 500 <= response.status_code < 600:
                _LOGGER.warning(
                    "seed_sources.fetch_transient",
                    extra={
                        "event": "seed_sources.fetch_transient",
                        "url": url,
                        "status": response.status_code,
                        "attempt": attempt + 1,
                        "backoff_s": backoff,
                    },
                )
                time.sleep(backoff)
                continue
            response.raise_for_status()
    raise RuntimeError(
        f"polite_get gave up on {url} after {retries} attempts; "
        f"last status={last_status} last_exc={last_exc!r}"
    )


def _same_origin_referer(url: str) -> str | None:
    """Return ``scheme://host/`` for use as a same-origin Referer header.

    Cheap protection against bot gates that 403 requests with no
    Referer or a Referer from a different host. Returns ``None``
    when the URL doesn't parse, in which case we send no header at
    all (better than a wrong one).
    """
    try:
        parsed = httpx.URL(url)
    except Exception:  # noqa: BLE001
        return None
    return f"{parsed.scheme}://{parsed.host}/"


def parse_html(html: str) -> HTMLParser:
    """Tiny wrapper around :class:`selectolax.parser.HTMLParser`.

    Exists so scrapers can ``from _common import parse_html`` instead
    of importing selectolax directly — that keeps the parser
    swappable if we ever migrate to beautifulsoup or lxml.
    """
    return HTMLParser(html)


def write_csv(entries: list[SeedEntry], filename: str) -> Path:
    """Persist entries to ``data/seed_lists/{filename}``.

    Idempotent — overwrites any existing file. Empty entries are
    dropped silently so a scraper that fails to extract a row
    doesn't poison the CSV with blank lines.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / filename
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["artist", "title", "year", "source_rank"])
        for entry in entries:
            if not entry.artist or not entry.title:
                continue
            writer.writerow(
                [
                    entry.artist,
                    entry.title,
                    entry.year if entry.year else "",
                    entry.source_rank if entry.source_rank else "",
                ]
            )
    _LOGGER.info(
        "seed_sources.csv_written",
        extra={
            "event": "seed_sources.csv_written",
            "path": str(path),
            "rows": len(entries),
        },
    )
    return path


__all__ = ["OUTPUT_DIR", "SeedEntry", "parse_html", "polite_get", "write_csv"]
