#!/usr/bin/env bash
# packages/shared-types/scripts/codegen.sh
#
# Dump the FastAPI OpenAPI schema and regenerate the TypeScript types
# consumed by @auxd/shared-types. Run locally with:
#
#   pnpm --filter @auxd/shared-types codegen
#
# CI runs `codegen:check` which additionally exits non-zero if the file
# is out of date (i.e., a backend schema change was not paired with a
# regenerated TS file) — see .github/workflows/codegen.yml.
#
# The script imports the FastAPI app in-process (no uvicorn boot needed)
# and reads the OpenAPI document via app.openapi(). Settings construction
# is deferred to the lifespan, so this path runs without any env vars.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_DIR/../.." && pwd)"
API_DIR="$REPO_ROOT/apps/api"

OUT_FILE="$PACKAGE_DIR/src/api.ts"
TMP_JSON="$(mktemp -t auxd-openapi-XXXXXX.json)"
trap 'rm -f "$TMP_JSON"' EXIT

echo "▶ Dumping OpenAPI schema from auxd_api.main:app …"
(
  cd "$API_DIR"
  uv run python -c "
import json, sys
from auxd_api.main import app
json.dump(app.openapi(), sys.stdout, indent=2, sort_keys=True)
"
) > "$TMP_JSON"

echo "▶ Generating TypeScript types via openapi-typescript …"
pnpm --filter @auxd/shared-types exec openapi-typescript "$TMP_JSON" \
  --output "$OUT_FILE" \
  --root-types \
  --root-types-no-schema-prefix

echo "✔ Wrote $OUT_FILE"
