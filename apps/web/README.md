# @spinz/web

Next.js 15 (App Router) frontend for Spinz. pnpm-managed within the monorepo.

## Quick start

```bash
# From the monorepo root
pnpm install
pnpm web:dev
# Open http://localhost:3000
```

## Test, lint, type-check

```bash
pnpm web:lint          # Biome
pnpm web:typecheck     # tsc --noEmit (strict)
pnpm web:build         # Production build
```

## File layout (deferred to subsequent tasks)

See `features/001-spinz-mvp/plan.md` §1.2 + §7 for the target structure
(route groups `(auth)`, `(onboarding)`, `(app)`; component tree; data
fetching patterns). Current scaffold is the minimum needed to verify the
monorepo + shared-types resolution, per task T003.
