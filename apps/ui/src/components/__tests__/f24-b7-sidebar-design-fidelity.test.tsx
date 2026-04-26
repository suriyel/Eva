/**
 * Feature #24 B7 — Sidebar v1.0.0 chip + Run selector + Runtime card + a11y.
 *
 * Traces To
 * =========
 *   B7-P1  §VRC v1.0.0 chip                                        UI/render
 *   B7-P2  §VRC current run selector                                UI/render
 *   B7-P3  §VRC Runtime status card                                 UI/render
 *   B7-N1  UCD §2.1 / NFR-011 / VRC B7 — collapsed nav a11y labels  UI/a11y
 *   B7-N2  UCD §2.1 Tab navigation focus ring (NFR-011 regression)  UI/a11y
 *   §Implementation Summary B7
 *
 * Rule 4 wrong-impl challenge:
 *   - 「v1.0.0 chip 缺失」                                       → B7-P1 fail
 *   - 「current run selector 不渲染 mono ticket id」              → B7-P2 fail
 *   - 「Runtime status card 缺失或不读 cli_versions」              → B7-P3 fail
 *   - 「collapsed=true 时 nav div 缺 title/aria-label」           → B7-N1 fail
 *
 * Rule 5 layer:
 *   [unit] uses fetch mocks (for useHealth + useCurrentRun); SUT real-imported.
 *
 * Red 阶段：当前 sidebar.tsx 仅 brand + 8 nav items；缺 v1.0.0 chip、缺 current
 *   run selector、缺 Runtime status card；nav div 在 collapsed=true 时也缺
 *   title/aria-label。每个测试的具体 selector 都会 FAIL.
 *
 * Feature ref: feature 24
 *
 * [unit] — uses fetch mocks for useHealth + useCurrentRun; jsdom.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, waitFor } from "@testing-library/react";
import * as React from "react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Sidebar } from "@/components/sidebar";

const originalFetch = globalThis.fetch;

function Wrapper({ children }: { children: React.ReactNode }): React.ReactElement {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  (globalThis as unknown as { __HARNESS_API_BASE__: string }).__HARNESS_API_BASE__ =
    "http://127.0.0.1:8765";
  // Reset viewport to wide (collapsed=false) by default.
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 1440 });
  window.dispatchEvent(new Event("resize"));
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

function withFetch(handler: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>): ReturnType<typeof vi.fn> {
  const fn = vi.fn(handler);
  globalThis.fetch = fn as unknown as typeof globalThis.fetch;
  return fn;
}

const HEALTH_BODY = {
  bind: "127.0.0.1",
  version: "1.0.0",
  claude_auth: { cli_present: true, authenticated: true, source: "config" },
  cli_versions: { claude: "claude/1.2", opencode: "opencode/0.5" },
};

const CURRENT_RUN_BODY = {
  run_id: "run-26.04.21-001",
  state: "running",
};

function defaultHandler(input: RequestInfo | URL, _init?: RequestInit): Promise<Response> {
  const url = String(input);
  if (url.includes("/api/health")) {
    return Promise.resolve(new Response(JSON.stringify(HEALTH_BODY), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }));
  }
  if (url.includes("/api/runs/current")) {
    return Promise.resolve(new Response(JSON.stringify(CURRENT_RUN_BODY), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }));
  }
  return Promise.resolve(new Response(JSON.stringify({}), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  }));
}

// --------------------------------------------------------------------- B7-P1
describe("B7-P1 UI/render — v1.0.0 chip in brand area", () => {
  it("非 collapsed 时 [data-testid='version-chip'] textContent === v1.0.0", async () => {
    withFetch(defaultHandler);
    const { container } = render(<Sidebar active="overview" />, { wrapper: Wrapper });
    await waitFor(() => {
      const chip = container.querySelector('[data-testid="version-chip"]');
      expect(chip, "version-chip missing in non-collapsed brand area").not.toBeNull();
      // textContent must read v1.0.0 (the design literal).
      expect(chip!.textContent?.trim(), `version-chip textContent: ${chip!.textContent}`).toBe("v1.0.0");
    });
  });
});

// --------------------------------------------------------------------- B7-P2
describe("B7-P2 UI/render — current run selector with mono ticket id", () => {
  it("currentRunId='run-26.04.21-001' → selector visible + <code class='mono'> textContent 严格匹配", async () => {
    withFetch(defaultHandler);
    const { container } = render(<Sidebar active="overview" />, { wrapper: Wrapper });
    await waitFor(() => {
      const sel = container.querySelector('[data-testid="current-run-selector"]');
      expect(sel, "current-run-selector missing").not.toBeNull();
      // Must contain a <code> with the run id and a label "当前 Run".
      const codeEl = sel!.querySelector("code");
      expect(codeEl, "selector mono <code> missing").not.toBeNull();
      expect(codeEl!.textContent?.trim()).toBe("run-26.04.21-001");
      // Label "当前 Run" present.
      expect(sel!.textContent ?? "", `selector textContent: ${sel!.textContent}`).toMatch(
        /当前 Run/,
      );
    });
  });
});

// --------------------------------------------------------------------- B7-P3
describe("B7-P3 UI/render — Runtime status card at sidebar footer", () => {
  it("[data-testid='runtime-status-card'] 含 'Runtime · 在线' + code-sm 'claude · opencode' + Power icon", async () => {
    withFetch(defaultHandler);
    const { container } = render(<Sidebar active="overview" />, { wrapper: Wrapper });
    await waitFor(() => {
      const card = container.querySelector('[data-testid="runtime-status-card"]');
      expect(card, "runtime-status-card missing").not.toBeNull();
      const text = card!.textContent ?? "";
      expect(text, `card textContent: ${text}`).toMatch(/Runtime\s*·\s*在线/);
      expect(text, `card missing 'claude · opencode': ${text}`).toMatch(/claude\s*·\s*opencode/);
      // Power icon — by SVG element presence (lucide-react / similar).
      const svg = card!.querySelector("svg");
      expect(svg, "Power SVG icon missing in runtime-status-card").not.toBeNull();
    });
  });
});

// --------------------------------------------------------------------- B7-N0 (extra)
describe("B7-N0 SEC/version-disclosure — version-chip MUST NOT leak full git SHA", () => {
  it("version-chip textContent 严格匹配 vN.N.N 格式 (不应嵌入 7+ 字符 hex SHA)", async () => {
    withFetch(defaultHandler);
    const { container } = render(<Sidebar active="overview" />, { wrapper: Wrapper });
    await waitFor(() => {
      const chip = container.querySelector('[data-testid="version-chip"]');
      expect(chip, "version-chip missing").not.toBeNull();
      const text = chip!.textContent ?? "";
      // Must look like vN.N.N (semver) — must NOT embed a 7+ char hex string
      // (which would suggest a leaked git SHA).
      const sha = text.match(/[a-f0-9]{7,}/);
      expect(sha, `version-chip leaked git SHA: ${sha?.[0]}`).toBeNull();
      expect(text, `version-chip not semver-shaped: ${text}`).toMatch(/^v\d+\.\d+\.\d+/);
    });
  });
});

// --------------------------------------------------------------------- B7-N1
describe("B7-N1 UI/a11y — collapsed=true nav items expose title + aria-label", () => {
  it("viewport=1200 (collapsed=true) → 每个 [data-testid^=nav-] 含 title + aria-label 非空", async () => {
    // Collapse trigger: viewport < 1280.
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 1200 });
    window.dispatchEvent(new Event("resize"));

    withFetch(defaultHandler);
    const { container } = render(<Sidebar active="overview" />, { wrapper: Wrapper });
    await waitFor(() => {
      const navs = container.querySelectorAll('[data-testid^="nav-"]');
      expect(navs.length, `expected 8 nav items, got ${navs.length}`).toBe(8);
      const offenders: string[] = [];
      navs.forEach((n) => {
        const title = (n as HTMLElement).getAttribute("title");
        const aria = (n as HTMLElement).getAttribute("aria-label");
        const id = (n as HTMLElement).getAttribute("data-testid") ?? "?";
        if (!title || title.trim() === "") offenders.push(`${id} missing title`);
        if (!aria || aria.trim() === "") offenders.push(`${id} missing aria-label`);
      });
      expect(offenders, `a11y violations: ${offenders.join("; ")}`).toHaveLength(0);
    });
  });
});

// --------------------------------------------------------------------- B7-N2
describe("B7-N2 UI/a11y — nav items keyboard-focusable (tabindex / button-like)", () => {
  it("每个 nav div 设置 tabindex≥0 或 role='button'，可被 Tab 焦点穿越", async () => {
    withFetch(defaultHandler);
    const { container } = render(<Sidebar active="overview" />, { wrapper: Wrapper });
    await waitFor(() => {
      const navs = container.querySelectorAll('[data-testid^="nav-"]');
      expect(navs.length).toBe(8);
      const offenders: string[] = [];
      navs.forEach((n) => {
        const el = n as HTMLElement;
        const tab = el.getAttribute("tabindex");
        const role = el.getAttribute("role");
        const id = el.getAttribute("data-testid") ?? "?";
        const focusable =
          (tab !== null && parseInt(tab, 10) >= 0) || role === "button" || el.tagName === "BUTTON";
        if (!focusable) offenders.push(`${id} not focusable (tabindex=${tab} role=${role} tag=${el.tagName})`);
      });
      expect(
        offenders,
        `nav items not keyboard-focusable: ${offenders.join("; ")}`,
      ).toHaveLength(0);
    });
  });
});
