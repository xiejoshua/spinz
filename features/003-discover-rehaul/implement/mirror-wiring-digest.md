# Implementation Digest — MB-mirror wiring into the live search path

**Feature:** 003-discover-rehaul
**Scope of this digest:** the four-point patch that finally turns the
populated Turso/libSQL mirror (1.3M MusicBrainz release-groups) into a
real participant in the request-time search pipeline. Prior phases of
003 built the ingest pipeline; this patch wires the mirror as Tier 0
of the search flow so users actually benefit from the catalog.

---

## Key decisions

1. **Mirror service is constructed in lifespan, injected per-request.**
   The `TursoClient` is opened once at app boot
   (`apps/api/src/auxd_api/main.py`) and stored on `app.state`. A
   thin `get_mirror_service` `Depends` helper in
   `apps/api/src/auxd_api/dependencies.py` wraps each request in a
   fresh `AlbumMirrorService` that shares the long-lived client.
   Rejected alternative: per-request `TursoClient` construction — would
   pay the SSL handshake on every search.

2. **Mirror disabled ⇒ no behaviour change.** Every consumer
   (`resolve_identity`, `search_albums`, `filter_only_search`,
   `search_albums_cached`) treats `mirror_service: AlbumMirrorService |
   None = None` and additionally checks `mirror_service.enabled`. When
   `TURSO_DATABASE_URL` is unset the constructor returns `None`, the
   service short-circuits, and the request falls through to Atlas +
   Discogs + MB API exactly as it did pre-mirror. This keeps the
   catalog-seed CLI, the arq worker, and the existing 26 search /
   identity tests untouched — none of them sets `app.state.mirror_client`.

3. **`search_albums` gains a Tier 0 before Atlas.** Mirror hits
   materialise into the local `Album` collection on first sight via
   `_resolve_or_materialise_mirror_row`, so subsequent searches for the
   same row short-circuit at the Mongo cache. The existing dedupe
   machinery (`_dedupe_alias_keys` / `_seen_*`) registers both the MBID
   key AND the title/artist key for every mirror hit, so the later
   Discogs and MB tiers correctly skip duplicates when they surface the
   same canonical album under a different identifier.

4. **`filter_only_search` uses the mirror SQL path when enabled.**
   Decade / genre / year-range browse mode previously paginated against
   our ~5k-row local catalog. With the mirror enabled and
   `require_cover=False`, browse paginates against the 1.3M-row mirror
   instead. `require_cover=True` still falls through to the Mongo path
   because the mirror doesn't carry `cover_art_url` today — that's the
   intentional v1 trade-off.

5. **`resolve_identity` consults the mirror between Mongo and the MB
   web API.** Sub-10ms libSQL hit vs ~1s MB API round-trip; on a mirror
   hit we materialise directly from `MirrorRow` and skip MB entirely.
   On a miss we fall through unchanged.

---

## Artifacts produced

### Modified
| Path | Change |
|------|--------|
| `apps/api/src/auxd_api/main.py` | Open / close `TursoClient` on lifespan; stash on `app.state.mirror_client`. |
| `apps/api/src/auxd_api/modules/albums/identity.py` | Added `_materialize_album_from_mirror`; added optional `mirror_service` param + mirror pre-check to `resolve_identity`. |
| `apps/api/src/auxd_api/modules/search/service.py` | Added `_resolve_or_materialise_mirror_row`; threaded `mirror_service` through `search_albums`, `search_albums_cached`, `filter_only_search`; added Tier 0 mirror search in `search_albums`; mirror SQL path in `filter_only_search`. |
| `apps/api/src/auxd_api/modules/search/routes.py` | Wired `Depends(get_mirror_service)` into the `search` route; passed through to `search_albums_cached` + `filter_only_search`. |
| `apps/api/src/auxd_api/modules/mb_mirror/service.py` | Added `filter_search()` + helpers (`_build_filter_where`, `_sort_clause_for`). |

### Created
| Path | Purpose |
|------|---------|
| `apps/api/src/auxd_api/dependencies.py` | Shared FastAPI `Depends` helpers — currently just `get_mirror_service`. |

### Removed / superseded
None. The patch is purely additive plus the optional `mirror_service`
parameter on existing public functions, all defaulting to `None`. No
clashing systems were identified — the mirror sits *above* the existing
Atlas / Discogs / MB chain rather than replacing any tier.

---

## Verification

* `uv run ruff check` — clean across all touched files.
* `uv run ruff format --check` — applied formatting fixes to two files.
* `uv run --extra dev pytest tests/integration/test_search_endpoint.py tests/unit/test_albums_identity.py` — **26 passed**.
* Full sweep (`tests/unit tests/integration`): 1062 passed, 3 skipped, 7
  failures pre-existing and unrelated (document-count counter,
  email/push adapter import-time registration, weekly digest dispatcher
  — none touch the search / mirror code paths).

---

## Open risks

1. **Materialisation pressure on `albums` collection.** Every fresh
   mirror hit issues a single-row insert into Mongo. v1 accepts the
   growth (the catalog grows monotonically with engagement). If churn
   becomes a concern we can introduce a TTL or rate-limit the
   materialisation gate.
2. **Cover-art gap in browse mode.** Mirror-backed filter-only browse
   surfaces albums without `cover_art_url` populated. The UI's
   `/api/cover/<mbid>` proxy fills the visual when an MBID is present
   (every mirror row has one) — so this is cosmetic only at v1, but
   worth a follow-up to backfill cover URLs.
3. **No mirror tests yet.** The mirror service has no dedicated unit
   coverage. The integration tests run with `mirror_service=None`, so
   the new code paths exercise only via manual smoke testing. A
   follow-up task should mock `AlbumMirrorService` to exercise the
   Tier 0 branches.
4. **Background-task probe still hits the live providers.** The
   `probe_external_for_filters` background task in `filter_only_search`
   was *not* updated to consult the mirror — it deliberately exercises
   Discogs + MB to grow the cover-art-bearing local catalog. That
   stays as designed but means thin local catalog → background fetch
   even when the mirror would have answered cheaply. Acceptable
   trade-off for now.

---

## Handoff notes

* **Code review focus:** double-check the dedup interaction in
  `search_albums` between Tier 0 mirror hits and Tier 2/3 fallbacks —
  the mirror hits register both MBID and title/artist alias keys, so
  later Discogs and MB hits for the same album should be suppressed
  on either key. If a duplicate slips through, that's where to look.
* **Manual smoke:** with `TURSO_DATABASE_URL` set, hit
  `GET /api/v1/search?q=ok+computer` and
  `GET /api/v1/search?decade=1990s` — should return mirror-sourced
  results in <100ms (vs ~1-25s pre-mirror on a cold query) and
  subsequent identical queries should be hot-cache fast.
* **No DB migration needed.** Mongo schema unchanged. The
  `cache_expires_at` field on materialised mirror rows reuses the
  existing 7-day TTL field, so the T064 refresh worker keeps them
  fresh.

Co-Authored-By: Joshua Xie
