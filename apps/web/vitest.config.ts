import path from "node:path";
import { defineConfig } from "vitest/config";

// Unit-test config (Node env — no JSDom). The helpers we currently test
// are mostly pure functions over plain objects, plus the review-body
// renderer which emits React nodes and is serialised through
// `react-dom/server.renderToStaticMarkup`. Modules that emit nodes call
// `createElement` directly (no JSX) so vitest's esbuild doesn't need a
// JSX transform — tsconfig.json keeps `jsx: preserve` for Next.js.
// If we add full DOM/component tests later, switch `environment` to
// "jsdom", install `@testing-library/react`, and add @vitejs/plugin-react
// (or set `esbuild: { jsx: "automatic", jsxImportSource: "react" }` here).
//
// REV-200 (Phase 6B code review): the `include` pattern is intentionally
// scoped to `tests/unit/**` so Playwright (`tests/e2e/**`),
// accessibility, and perf folders don't get picked up by vitest. A
// developer who accidentally drops a `*.test.ts`/`*.test.tsx` file
// outside `tests/unit/` would silently never have it run — `pnpm
// lint:test-location` (wired into CI) catches that case by failing the
// build when stray test files exist outside the include root.
export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  test: {
    environment: "node",
    include: ["tests/unit/**/*.test.ts", "tests/unit/**/*.test.tsx"],
    exclude: ["tests/e2e/**", "tests/a11y/**", "tests/perf/**", "node_modules/**", ".next/**"],
  },
});
