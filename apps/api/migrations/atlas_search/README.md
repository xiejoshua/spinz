# Atlas Search index artifacts

Atlas Search indexes are MongoDB Atlas-only resources that live alongside a
collection but are managed independently of the document schema. They are
**not** created by Beanie's `init_beanie` call and must be applied to each
cluster (dev / staging / prod) by an operator.

At MVP, application is **manual via the Atlas UI**. The Atlas Admin API
automation path is deferred to v1.x per
`features/001-auxd-mvp/migrations/migration-plan.md` — the maintenance cost
of keeping a programmatic applier in sync with Atlas API quirks is not yet
justified by the operational frequency (we apply each index once per cluster
and rarely touch them thereafter).

## Files

| File | Purpose | Target collection | Index name |
| --- | --- | --- | --- |
| `albums_index.json` | Free-text album search (plan §11.1) — title + artist_credit + artists.name + popularity_score boost. | `albums` | `albums_text_search` |

## How to apply (one-time per cluster)

1. Sign in to MongoDB Atlas → select the project → open the target cluster.
2. Navigate to **Search** (top tab on the cluster page) → **Create Search
   Index**.
3. Choose **JSON Editor** (not Visual Editor — the JSON in this directory is
   the source of truth).
4. Select the target collection from the dropdown (e.g. `albums` for
   `albums_index.json`).
5. Paste the contents of the matching JSON file into the editor.
6. Set the **Index Name** to match the `"name"` field at the top of the JSON
   (e.g. `albums_text_search`). The JSON `"name"` and the Atlas index name
   must match exactly so the backend's `$search` queries find the index.
7. Click **Create Search Index**. Atlas reports "Building" → "Active" after
   roughly 1–5 minutes for an empty / small collection.
8. Record the application in your team's runbook with cluster name and date.

## Verifying application

From the Atlas Search tab, the index should show **Status: Active** and the
field mappings should match this JSON. To verify from the backend, run a
sample `$search` aggregation pointed at the index name — a successful empty
result confirms the index is queryable.

## Modifying an index

Atlas Search indexes cannot be edited in place — they must be dropped and
recreated. To change a mapping:

1. Update the JSON file in this directory and commit.
2. In Atlas UI, drop the existing index (Search tab → ⋯ menu → Delete).
3. Recreate following the steps above using the updated JSON.

For non-trivial schema changes (renaming a field, changing analyzer), plan
the rollout as part of a normal data-model migration so the application
code is updated in lockstep.
