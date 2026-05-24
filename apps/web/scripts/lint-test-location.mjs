#!/usr/bin/env node
/**
 * REV-200 CI guard: fail the build if any *.test.ts or *.test.tsx file
 * lives outside `tests/unit/`.
 *
 * Vitest's `include` pattern only picks up `tests/unit/**`, so a test
 * placed in `tests/integration/` or `src/components/` would silently
 * never run. This script crawls the workspace (skipping node_modules,
 * .next, build outputs, test-results, and Playwright e2e/a11y/perf
 * directories) and exits non-zero if any stray test files exist.
 *
 * Run via `pnpm lint:test-location` — wired into CI after biome.
 */

import { readdirSync, statSync } from "node:fs";
import { join, posix, relative, sep } from "node:path";

const ROOT = process.cwd();

const PRUNE_DIRS = new Set([
  "node_modules",
  ".next",
  ".turbo",
  ".vercel",
  "dist",
  "build",
  "coverage",
  "test-results",
  "playwright-report",
  ".git",
]);

const ALLOWED_PREFIX = "tests/unit/";
const TEST_PATTERN = /\.test\.tsx?$/;

/**
 * Recursively walk `dir`, returning POSIX-style paths (relative to ROOT)
 * for every file whose name matches the test pattern.
 */
function walk(dir) {
  const matches = [];
  let entries;
  try {
    entries = readdirSync(dir, { withFileTypes: true });
  } catch (err) {
    if (err.code === "ENOENT") return matches;
    throw err;
  }
  for (const entry of entries) {
    if (entry.isDirectory()) {
      if (PRUNE_DIRS.has(entry.name)) continue;
      matches.push(...walk(join(dir, entry.name)));
    } else if (entry.isFile() && TEST_PATTERN.test(entry.name)) {
      const abs = join(dir, entry.name);
      const rel = relative(ROOT, abs).split(sep).join(posix.sep);
      matches.push(rel);
    }
  }
  return matches;
}

const allTestFiles = walk(ROOT);
const stray = allTestFiles.filter((p) => !p.startsWith(ALLOWED_PREFIX));

if (stray.length > 0) {
  console.error(
    `lint:test-location: found ${stray.length} *.test.ts(x) file(s) outside ${ALLOWED_PREFIX}:`
  );
  for (const p of stray) {
    console.error(`  - ${p}`);
  }
  console.error(
    "\nVitest's include pattern only matches tests/unit/**. Move these " +
      "files into tests/unit/ or rename them to .spec.ts(x) if they are " +
      "Playwright specs."
  );
  process.exit(1);
}

console.log(
  `lint:test-location: OK — all ${allTestFiles.length} *.test.ts(x) file(s) live under ${ALLOWED_PREFIX}`
);
