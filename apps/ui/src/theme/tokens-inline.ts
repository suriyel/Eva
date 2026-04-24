/**
 * Returns tokens.css as a raw string for runtime <style> injection.
 * In the browser (Vite build) `?raw` inlines the file; during vitest (Node ESM)
 * we fall back to reading directly from disk using `createRequire`.
 */
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore — `?raw` is a Vite virtual import.
import tokensCssRaw from "./tokens.css?raw";

let cached: string | null = null;

function loadSyncNode(): string {
  try {
    // createRequire works from ESM; typeof process guards the browser.
    if (typeof process === "undefined" || !process.versions?.node) return "";
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = eval("require")("node:module") as { createRequire: (m: string) => NodeRequire };
    const req = mod.createRequire(process.cwd() + "/");
    const fs = req("node:fs") as typeof import("node:fs");
    const path = req("node:path") as typeof import("node:path");
    const candidates = [
      path.resolve(process.cwd(), "src/theme/tokens.css"),
      path.resolve(process.cwd(), "apps/ui/src/theme/tokens.css"),
    ];
    for (const c of candidates) {
      if (fs.existsSync(c)) return fs.readFileSync(c, "utf8");
    }
  } catch {
    /* ignore */
  }
  return "";
}

export function getTokensCssText(): string {
  if (cached != null) return cached;
  const fromVite = typeof tokensCssRaw === "string" ? tokensCssRaw : "";
  if (fromVite.length > 0) {
    cached = fromVite;
    return cached;
  }
  cached = loadSyncNode();
  return cached;
}
