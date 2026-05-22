# auxd-api

FastAPI backend for auxd. uv-managed Python 3.12+.

## Quick start

```bash
cd apps/api
uv sync                              # install deps into .venv
uv run uvicorn auxd_api.main:app --reload --port 8000
# curl http://localhost:8000/healthz
```

## Test, lint, type-check

```bash
uv run pytest                        # tests
uv run ruff check .                  # lint
uv run ruff format --check .         # formatting check
uv run mypy src tests                # strict type-check
```

## Module layout (deferred to subsequent tasks)

See `features/001-auxd-mvp/plan.md` §1.2 for the full target structure.
Current scaffold contains only `main.py` (healthz + app factory) and a passing
healthz test, per task T003.
