import path from "node:path";
import { defineConfig } from "vitest/config";

// Unit-test config (Node env — no JSDom). The helpers we currently test
// are pure functions over plain objects; if we add component tests later,
// switch `environment` to "jsdom" and install @testing-library/react.
export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  test: {
    environment: "node",
    include: ["tests/unit/**/*.test.ts"],
    exclude: ["tests/e2e/**", "node_modules/**", ".next/**"],
  },
});
