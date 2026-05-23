# MongoDB Migrations

This directory holds out-of-band MongoDB migrations that must be applied
manually to an Atlas cluster — i.e. things that cannot be expressed as a
Beanie ``Document.Settings.indexes`` declaration and so are not picked up
by the ODM's first-write auto-init.

## Atlas Search indexes

Atlas Search indexes are **not** part of the standard Mongo index API and
cannot be created via PyMongo. They must be applied through the Atlas UI
or the ``atlas-cli`` once per cluster.

### Index inventory

| File | Collection | Notes |
|------|------------|-------|
| ``atlas_search/albums_index.json`` | ``albums`` | Free-text search over ``title`` + ``artist_credit`` with edge-N-gram autocomplete + popularity boost via ``log1p(rating_count)`` (T068) |

### Apply via Atlas UI (canonical at MVP)

1. Open the Atlas cluster → **Search** tab → **Create Search Index**.
2. Choose **JSON Editor**.
3. Set:
   - **Index name**: ``albums_text_search`` (must match the ``name``
     field at the top of ``atlas_search/albums_index.json`` — the
     application's ``$search`` calls reference this string).
   - **Database**: ``auxd_dev``
   - **Collection**: ``albums``
4. Paste **only the contents of the ``definition`` block** into the
   JSON-body editor — i.e. drop the outer ``{"name": ..., "definition":
   {...}}`` wrapper. The UI takes the name from the field above and
   expects only the definition shape in the body. (The full
   ``{name, definition}`` wrapper is the ``atlas-cli`` format, not the
   UI format.)
5. Submit. Index build typically completes in ~1 minute on a small
   catalog. Status flips ``BUILDING → STEADY``; once ``STEADY``,
   ``GET /api/v1/search`` will hit the Atlas tier first.

### Apply via MongoDB Atlas CLI (automation)

> ⚠️ **Binary-name collision warning.** The MongoDB Atlas CLI installs
> a binary called ``atlas``. **A separate, unrelated tool from ariga.io
> (a SQL schema-migration tool) also installs a binary called
> ``atlas``.** If you ran ``brew install atlas`` you got the ariga one;
> its top-level commands are ``copilot / login / migrate / schema``
> with no ``clusters`` subcommand. To get the MongoDB Atlas CLI:
>
> ```bash
> brew install mongodb-atlas-cli
> # If ariga atlas is already linked, unlink it first:
> brew unlink atlas
> brew link mongodb-atlas-cli
> ```
>
> Or symlink the MongoDB binary as ``mongo-atlas`` to keep both
> co-resident.

For CI / staging-promotion pipelines (assumes the MongoDB ``atlas`` CLI
is installed and logged in via ``atlas login``):

```bash
atlas clusters search indexes create \
  --clusterName "main" \
  --file apps/api/migrations/atlas_search/albums_index.json
```

The ``--file`` flag accepts the **full** ``{name, definition}`` wrapper
JSON. Idempotency: if an index with the same name already exists, the
CLI returns an error; use ``atlas clusters search indexes update
--indexId <id> --file apps/api/migrations/atlas_search/albums_index.json``
to modify an existing index instead.

### Search behavior

Once applied, the index supports:

* **Free-text + autocomplete** — ``title`` and ``artist_credit`` carry
  both ``string`` and ``autocomplete`` (edge-N-gram, 2-8 chars) field
  shapes, so queries can use either via the appropriate ``$search``
  operator.
* **Diacritic folding** — autocomplete fields set
  ``foldDiacritics=true`` so "beyonce" matches "Beyoncé".
* **Popularity boost** — search scores are scaled by ``log1p(rating_count)``
  via the ``scoreDetails`` block, so albums with more local diary
  activity surface above sparsely-rated peers at equal text relevance.
* **Stored source** — ``title``, ``artist_credit``, ``artists.name``,
  ``cover_art_url``, and ``release_year`` are returned in search hits
  without a follow-up ``findOne`` round-trip.
