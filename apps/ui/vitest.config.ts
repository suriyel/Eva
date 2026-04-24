import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Vitest 配置——happy-dom 提供 DOM；testing-library/jest-dom 由 setup 注入
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  test: {
    globals: true,
    environment: "happy-dom",
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
    css: false,
    coverage: {
      provider: "v8",
      reporter: ["text", "text-summary", "json-summary"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.test.{ts,tsx}",
        "src/**/__tests__/**",
        "src/__sanity__/**",
        "src/test-setup.ts",
        "src/main.tsx",
        "src/theme/tokens.css",
        // tokens-inline.ts is a build-environment shim that delegates to Vite's
        // `?raw` import in browser/vitest and to `fs.readFileSync` via a
        // `createRequire` fallback in Node dev scripts. The Node-fallback branch
        // is unreachable under Vite bundling (`?raw` always resolves), and the
        // behavior tests (tokens-fidelity.test.ts + app-shell render tests)
        // exercise the public getTokensCssText() contract. Excluding here keeps
        // coverage metrics honest: we would otherwise need contrived mocks to
        // reach code that cannot execute in the test environment.
        "src/theme/tokens-inline.ts",
        "**/*.d.ts",
        "**/*.html",
      ],
      thresholds: {
        lines: 90,
        branches: 80,
        functions: 90,
        statements: 90,
      },
    },
  },
});
