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

### Apply via Atlas UI

1. Open the Atlas cluster → **Search** tab → **Create Index**.
2. Choose **JSON Editor**.
3. Select the target database + collection (``albums``).
4. Paste the contents of ``atlas_search/albums_index.json`` and name the
   index ``albums_text_search`` (must match the ``name`` field in the JSON
   so the application code can reference it).
5. Submit. Index build typically completes in ~1 minute on a small
   catalog.

### Apply via atlas-cli (automation)

For CI / staging-promotion pipelines:

```bash
atlas clusters search indexes create \
  --clusterName "<cluster-name>" \
  --file apps/api/migrations/atlas_search/albums_index.json
```

The ``--file`` flag accepts the same JSON document used in the UI flow.
Idempotency: if an index with the same name already exists, the CLI
returns an error; use ``atlas clusters search indexes update --indexId
<id>`` to modify an existing index instead.

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
