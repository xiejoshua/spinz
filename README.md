# Spinz

Social album-tracking platform — log albums in <8 seconds, discover from the people you follow.

> Active feature: **001-spinz-mvp**. See [features/001-spinz-mvp/README.md](features/001-spinz-mvp/README.md) for the full lifecycle status.

## Monorepo layout

```
spinz/
├── apps/
│   ├── api/                  FastAPI backend (uv-managed, Python 3.12+)
│   └── web/                  Next.js 15 frontend (pnpm-managed, React 19)
├── packages/
│   └── shared-types/         TS types codegenned from FastAPI OpenAPI (T028)
├── features/                 Product Forge feature folders
└── .specify/memory/          Project constitution (ratified 2026-05-22)
```

## Tooling prerequisites

| Tool | Why | Install |
|------|-----|---------|
| Node 20+ | `apps/web` runtime | `brew install node` (or `nvm`) |
| pnpm 9+ | workspace orchestration | `brew install pnpm` |
| Python 3.12+ | `apps/api` runtime | `brew install python@3.12` |
| uv | Python package manager | `brew install uv` |

## Quick start (all)

```bash
# Frontend
pnpm install
pnpm web:dev                  # http://localhost:3000

# Backend (separate terminal)
cd apps/api
uv sync
uv run uvicorn spinz_api.main:app --reload --port 8000
# http://localhost:8000/healthz
```

## Constitution

Six non-negotiable principles in [.specify/memory/constitution.md](.specify/memory/constitution.md):

1. External-call resilience (retry + timeout + circuit-breaker)
2. Schema-versioned MongoDB documents (lazy upgrade)
3. Library-first modules (no god-objects)
4. Test-first for catalog/auth edges
5. Observability mandatory (logs + PostHog + Sentry + OTel)
6. Provider abstraction (`MusicProvider` interface — no direct SDK imports in features)

Every PR review checks these. Amendments require ADR + founder sign-off.

## Product Forge lifecycle

Spinz uses [Product Forge](.claude/skills/speckit-product-forge-forge/) for the full feature lifecycle. Status of the current feature:

```bash
# Lifecycle status of the active feature
/speckit.product-forge.status
```
