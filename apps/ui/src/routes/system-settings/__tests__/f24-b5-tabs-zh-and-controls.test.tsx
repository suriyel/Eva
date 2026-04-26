/**
 * Feature #24 B5 — SystemSettings 5 Tab 中文化 + 控件大幅补齐 (设计稿对照).
 *
 * Traces To
 * =========
 *   B5-P1  §VRC 5 tabs 中文化 / NFR-010                          UI/render
 *   B5-P2  §VRC model tab / FR-019 / FR-020                      UI/render
 *   B5-P3  §VRC auth tab / FR-032                                UI/render
 *   B5-P4  §VRC classifier tab / FR-021 / FR-023 Wave 3          UI/render
 *   B5-P5  §VRC mcp tab                                          UI/render
 *   B5-P6  §VRC ui tab / UCD §2.8 ui_density                     UI/render
 *   B5-N1  NFR-008 / FR-032 SEC — auth tab DOM 不含明文 key       SEC/api-key-leak
 *   B5-N2  FR-021 SSRF / IFR-004                                  FUNC/error
 *   B5-P7  IAPI-002 PUT /api/settings/classifier                  INTG/api
 *   §Implementation Summary B5
 *
 * Rule 4 wrong-impl challenge:
 *   - 「tab label 仍英文 (Models/ApiKey/...)」                       → B5-P1 fail
 *   - 「model tab 占位文本无 SettingsSection」                       → B5-P2 fail
 *   - 「auth tab 仅 1 个 input」                                     → B5-P3 fail
 *   - 「classifier 缺 enabled / provider / model_name 字段」          → B5-P4 fail
 *   - 「mcp 占位文本」                                               → B5-P5 fail
 *   - 「ui tab 占位文本」                                            → B5-P6 fail
 *   - 「mutation 漏 strict_schema_override 字段」                    → B5-P7 fail
 *
 * Rule 5 layer:
 *   [unit] uses fetch mocks; SystemSettingsPage real-imported.
 *   Real test for backend round-trip lives in F22 real_settings_consumer.
 *
 * Red 阶段：当前 system-settings/index.tsx:22-28 TABS 是 [Models/ApiKey/Classifier/MCP/UI]
 *   英文 → B5-P1 严格匹配中文 fail；mcp/ui tab 占位文本 → B5-P5/P6 fail；
 *   model tab `<p>placeholder</p>` → B5-P2 fail。
 *
 * Feature ref: feature 24
 *
 * [unit] — uses fetch mocks; jsdom.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/react";
import * as React from "react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SystemSettingsPage } from "@/routes/system-settings";

const originalFetch = globalThis.fetch;

function Wrapper({ children }: { children: React.ReactNode }): React.ReactElement {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/settings"]}>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  (globalThis as unknown as { __HARNESS_API_BASE__: string }).__HARNESS_API_BASE__ =
    "http://127.0.0.1:8765";
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

const GENERAL_BODY = {
  api_key_ref: { service: "harness-classifier", user: "default" },
  api_key_masked: "***old",
  keyring_backend: "native" as const,
  mcp_servers: [
    { name: "fs", endpoint: "http://localhost:7000", status: "running" },
    { name: "git", endpoint: "http://localhost:7001", status: "stopped" },
  ],
  ui_density: "default" as const,
};

const CLASSIFIER_BODY = {
  enabled: true,
  provider: "GLM" as const,
  model_name: "glm-4.6",
  api_key_ref: { service: "harness-classifier", user: "default" },
  base_url: "https://open.bigmodel.cn/api/paas/v4/",
  strict_schema_override: null,
};

function withFetch(handler: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>): ReturnType<typeof vi.fn> {
  const fn = vi.fn(handler);
  globalThis.fetch = fn as unknown as typeof globalThis.fetch;
  return fn;
}

function defaultHandler(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const url = String(input);
  if (url.includes("/api/settings/general")) {
    return Promise.resolve(
      new Response(JSON.stringify(GENERAL_BODY), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
  }
  if (url.includes("/api/settings/classifier")) {
    return Promise.resolve(
      new Response(JSON.stringify(CLASSIFIER_BODY), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
  }
  return Promise.resolve(
    new Response(JSON.stringify({}), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

// --------------------------------------------------------------------- B5-P1
describe("B5-P1 UI/render — 5 tabs 中文化 (NFR-010)", () => {
  it("5 vertical tabs textContent 严格匹配 [模型与 Provider, API Key 与认证, Classifier, 全局 MCP, 界面偏好]", async () => {
    withFetch(defaultHandler);
    const { container } = render(<SystemSettingsPage />, { wrapper: Wrapper });
    await waitFor(() => {
      // Find tab elements by data-testid (per VRC).
      const tabIds = ["model", "auth", "classifier", "mcp", "ui"];
      const labels = tabIds.map((id) => {
        const el = container.querySelector(`[data-testid="tab-${id}"]`);
        return el?.textContent?.trim() ?? null;
      });
      expect(labels, `tabs not all rendered: ${JSON.stringify(labels)}`).toEqual([
        "模型与 Provider",
        "API Key 与认证",
        "Classifier",
        "全局 MCP",
        "界面偏好",
      ]);
    });
  });
});

// --------------------------------------------------------------------- B5-P2
describe("B5-P2 UI/render — model tab 含 2 SettingsSection + 4 列 Grid Table", () => {
  it("切到 model tab → run-default-models section + model-rules-table 5 列表头 + 「新增规则」 button", async () => {
    withFetch(defaultHandler);
    const { container } = render(<SystemSettingsPage />, { wrapper: Wrapper });
    const modelTab = await waitFor(() => {
      const t = container.querySelector('[data-testid="tab-model"]');
      expect(t, "tab-model missing").not.toBeNull();
      return t as Element;
    });
    fireEvent.click(modelTab);
    await waitFor(() => {
      const runDefaults = container.querySelector('[data-section="run-default-models"]');
      expect(runDefaults, "run-default-models section missing").not.toBeNull();
      const table = container.querySelector('table[data-testid="model-rules-table"]');
      expect(table, "model-rules-table missing").not.toBeNull();
      // Table headers (4 visible: Skill 匹配 / 工具 / 模型 / actions).
      const ths = Array.from(table!.querySelectorAll("th")).map((th) => th.textContent?.trim());
      expect(ths, `header columns: ${JSON.stringify(ths)}`).toEqual(
        expect.arrayContaining(["Skill 匹配", "工具", "模型", "actions"]),
      );
      const addBtn = container.querySelector('button[data-testid="add-model-rule"]');
      expect(addBtn?.textContent, "add-model-rule button label").toMatch(/新增规则/);
    });
  });
});

// --------------------------------------------------------------------- B5-P3
describe("B5-P3 UI/render — auth tab 含 2 MaskedInput + 测试 2 个 Provider button", () => {
  it("切到 auth tab → anthropic-key 行 + opencode-key 行 + test-conn-2providers button", async () => {
    withFetch(defaultHandler);
    const { container } = render(<SystemSettingsPage />, { wrapper: Wrapper });
    const tab = await waitFor(() => {
      const t = container.querySelector('[data-testid="tab-auth"]');
      expect(t, "tab-auth missing").not.toBeNull();
      return t as Element;
    });
    fireEvent.click(tab);
    await waitFor(() => {
      const anth = container.querySelector('[data-row="anthropic-key"]');
      expect(anth, "anthropic-key row missing").not.toBeNull();
      const opc = container.querySelector('[data-row="opencode-key"]');
      expect(opc, "opencode-key row missing").not.toBeNull();
      const test = container.querySelector('button[data-testid="test-conn-2providers"]');
      expect(test, "test-conn-2providers button missing").not.toBeNull();
    });
  });
});

// --------------------------------------------------------------------- B5-P4
describe("B5-P4 UI/render — classifier tab 全字段表单", () => {
  it("切到 classifier tab → enabled / provider / model_name / api_key_ref / base_url / strict_schema_override 全部 visible", async () => {
    withFetch(defaultHandler);
    const { container } = render(<SystemSettingsPage />, { wrapper: Wrapper });
    const tab = await waitFor(() => {
      const t = container.querySelector('[data-testid="tab-classifier"]');
      expect(t, "tab-classifier missing").not.toBeNull();
      return t as Element;
    });
    fireEvent.click(tab);
    const required = [
      'enabled',
      'provider',
      'model_name',
      'api_key_ref',
      'base_url',
      'strict_schema_override',
    ];
    await waitFor(() => {
      const missing = required.filter(
        (key) => container.querySelector(`[data-row="${key}"]`) == null,
      );
      expect(missing, `classifier rows missing: ${missing.join(",")}`).toHaveLength(0);
    });
  });
});

// --------------------------------------------------------------------- B5-P5
describe("B5-P5 UI/render — mcp tab 列表渲染 mcp_servers", () => {
  it("切到 mcp tab + GET /api/settings/general 含 mcp_servers=2 → 2 行 visible", async () => {
    withFetch(defaultHandler);
    const { container } = render(<SystemSettingsPage />, { wrapper: Wrapper });
    const tab = await waitFor(() => {
      const t = container.querySelector('[data-testid="tab-mcp"]');
      expect(t, "tab-mcp missing").not.toBeNull();
      return t as Element;
    });
    fireEvent.click(tab);
    await waitFor(() => {
      const list = container.querySelector('[data-testid="mcp-servers-list"]');
      expect(list, "mcp-servers-list missing").not.toBeNull();
      const rows = list!.querySelectorAll('[data-mcp-row]');
      expect(rows.length, `expected 2 mcp rows, got ${rows.length}`).toBe(2);
      // Row content reflects fixture (server name visible).
      const text = list!.textContent ?? "";
      expect(text, `mcp list textContent missing 'fs' or 'git': ${text}`).toMatch(/fs/);
      expect(text).toMatch(/git/);
    });
  });
});

// --------------------------------------------------------------------- B5-P6
describe("B5-P6 UI/render — ui tab ui_density SegmentedControl + prefers-reduced-motion chip", () => {
  it("切到 ui tab → ui-density 行 (3 段) + prefers-reduced-motion 行", async () => {
    withFetch(defaultHandler);
    const { container } = render(<SystemSettingsPage />, { wrapper: Wrapper });
    const tab = await waitFor(() => {
      const t = container.querySelector('[data-testid="tab-ui"]');
      expect(t, "tab-ui missing").not.toBeNull();
      return t as Element;
    });
    fireEvent.click(tab);
    await waitFor(() => {
      const dens = container.querySelector('[data-row="ui-density"]');
      expect(dens, "ui-density row missing").not.toBeNull();
      // Three segments: compact / default / comfortable.
      const segText = dens!.textContent ?? "";
      for (const seg of ["compact", "default", "comfortable"]) {
        expect(segText, `ui-density segment ${seg} missing in textContent: ${segText}`).toMatch(
          new RegExp(seg),
        );
      }
      const prm = container.querySelector('[data-row="prefers-reduced-motion"]');
      expect(prm, "prefers-reduced-motion row missing").not.toBeNull();
    });
  });
});

// --------------------------------------------------------------------- B5-N0a (extra)
describe("B5-N0a FUNC/error — model tab id NOT renamed back to 'models' (NFR-010 enforcement)", () => {
  it("tab id 集合严格 [model, auth, classifier, mcp, ui]，旧 'models'/'apikey' 标签必须不存在", async () => {
    withFetch(defaultHandler);
    const { container } = render(<SystemSettingsPage />, { wrapper: Wrapper });
    await waitFor(() => {
      // First require the new tabs to exist (fix introduced).
      const newModel = container.querySelector('[data-testid="tab-model"]');
      const newAuth = container.querySelector('[data-testid="tab-auth"]');
      expect(newModel, "tab-model (singular) not present — fix not applied").not.toBeNull();
      expect(newAuth, "tab-auth not present — fix not applied").not.toBeNull();
      // And confirm the old singular-vs-plural drift is purged (also under
      // any data-tab-id alternate selector used by F22 prior code).
      const oldModelsByTestId = container.querySelector('[data-testid="tab-models"]');
      const oldModelsByTabId = container.querySelector('[data-tab-id="models"]');
      const oldApikeyByTestId = container.querySelector('[data-testid="tab-apikey"]');
      const oldApikeyByTabId = container.querySelector('[data-tab-id="apikey"]');
      expect(oldModelsByTestId, "old 'tab-models' (英文复数) still present (data-testid)").toBeNull();
      expect(oldModelsByTabId, "old 'data-tab-id=models' still present").toBeNull();
      expect(oldApikeyByTestId, "old 'tab-apikey' still present (data-testid)").toBeNull();
      expect(oldApikeyByTabId, "old 'data-tab-id=apikey' still present").toBeNull();
    });
  });
});

// --------------------------------------------------------------------- B5-N1
describe("B5-N1 SEC/api-key-leak — auth tab DOM 不含明文 key", () => {
  it("auth tab 渲染后 document.body.outerHTML grep 32+ 字符 alphanumeric token 0 命中", async () => {
    // GET returns api_key_masked '***xyz' — never plaintext.
    withFetch((input) => {
      const url = String(input);
      if (url.includes("/api/settings/general")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              ...GENERAL_BODY,
              api_key_masked: "***xyz",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      return defaultHandler(input);
    });
    const { container } = render(<SystemSettingsPage />, { wrapper: Wrapper });
    const tab = await waitFor(() => {
      const t = container.querySelector('[data-testid="tab-auth"]');
      expect(t, "tab-auth missing").not.toBeNull();
      return t as Element;
    });
    fireEvent.click(tab);
    await waitFor(() => {
      const anth = container.querySelector('[data-row="anthropic-key"]');
      expect(anth).not.toBeNull();
    });
    const html = (container.ownerDocument?.body.outerHTML ?? container.outerHTML).toString();
    // 32+ char alphanumeric token would be a leaked plaintext key.
    const longTokens = html.match(/\b[a-zA-Z0-9]{32,}\b/g) ?? [];
    expect(longTokens, `plaintext-like tokens in DOM: ${JSON.stringify(longTokens)}`).toHaveLength(0);
  });
});

// --------------------------------------------------------------------- B5-N2
describe("B5-N2 FUNC/error — classifier tab 内网 base_url 触发 mutation error 状态", () => {
  it("base_url=`http://internal-attacker:6379` + 保存 → backend 422 → UI 暴露 error", async () => {
    let putCalled = false;
    withFetch((input, init) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      if (url.includes("/api/settings/classifier") && method === "PUT") {
        putCalled = true;
        return Promise.resolve(
          new Response(
            JSON.stringify({
              detail: { error_code: "SSRF_REJECTED", field: "base_url" },
            }),
            { status: 422, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      return defaultHandler(input, init);
    });
    const { container } = render(<SystemSettingsPage />, { wrapper: Wrapper });
    const tab = await waitFor(() => {
      const t = container.querySelector('[data-testid="tab-classifier"]');
      expect(t).not.toBeNull();
      return t as Element;
    });
    fireEvent.click(tab);
    const baseUrlRow = await waitFor(() => {
      const r = container.querySelector('[data-row="base_url"]');
      expect(r, "classifier base_url row missing").not.toBeNull();
      return r as Element;
    });
    const input = baseUrlRow.querySelector("input");
    expect(input, "base_url input missing").not.toBeNull();
    fireEvent.change(input as HTMLInputElement, {
      target: { value: "http://internal-attacker:6379" },
    });
    // Submit (the save button id is implementation-defined; we look for first button under
    // the tab body).
    const saveBtn = container.querySelector('button[data-testid="classifier-save"]');
    expect(saveBtn, "classifier-save button missing").not.toBeNull();
    fireEvent.click(saveBtn as Element);
    await waitFor(() => {
      expect(putCalled, "PUT /api/settings/classifier not invoked").toBe(true);
    });
    await new Promise((r) => setTimeout(r, 50));
    // After 422, an error indicator must be visible (we accept any [data-error] surface).
    const errSurfaces = container.querySelectorAll('[data-error="true"], [role="alert"]');
    expect(
      errSurfaces.length,
      "no error surface after 422 — silent SSRF",
    ).toBeGreaterThanOrEqual(1);
  });
});

// --------------------------------------------------------------------- B5-P7
describe("B5-P7 INTG/api — PUT /api/settings/classifier 携带 strict_schema_override 字段", () => {
  it("修改 strict_schema_override 后 PUT request body 含该字段", async () => {
    let lastBody: unknown = null;
    withFetch((input, init) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      if (url.includes("/api/settings/classifier") && method === "PUT") {
        const raw = init?.body;
        try {
          lastBody = typeof raw === "string" ? JSON.parse(raw) : raw;
        } catch {
          lastBody = raw;
        }
        return Promise.resolve(
          new Response(JSON.stringify({ ...CLASSIFIER_BODY, strict_schema_override: true }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      return defaultHandler(input, init);
    });
    const { container } = render(<SystemSettingsPage />, { wrapper: Wrapper });
    const tab = await waitFor(() => {
      const t = container.querySelector('[data-testid="tab-classifier"]');
      expect(t).not.toBeNull();
      return t as Element;
    });
    fireEvent.click(tab);
    const strictRow = await waitFor(() => {
      const r = container.querySelector('[data-row="strict_schema_override"]');
      expect(r, "strict_schema_override row missing").not.toBeNull();
      return r as Element;
    });
    // Click the "true" radio (any input with value="true" inside this row).
    const radios = strictRow.querySelectorAll('input[type="radio"]');
    expect(radios.length, `expected 3 radio (null/true/false), got ${radios.length}`).toBeGreaterThanOrEqual(3);
    const trueRadio = Array.from(radios).find(
      (r) => (r as HTMLInputElement).value === "true",
    ) as HTMLInputElement | undefined;
    expect(trueRadio, "no value='true' radio in strict_schema_override row").not.toBeUndefined();
    fireEvent.click(trueRadio!);
    const saveBtn = container.querySelector('button[data-testid="classifier-save"]') as Element | null;
    expect(saveBtn, "classifier-save missing").not.toBeNull();
    fireEvent.click(saveBtn!);
    await waitFor(() => {
      expect(lastBody, "PUT body not captured").not.toBeNull();
      const body = lastBody as Record<string, unknown>;
      expect(Object.keys(body), `body keys: ${JSON.stringify(Object.keys(body))}`).toContain(
        "strict_schema_override",
      );
      expect(body.strict_schema_override, `strict_schema_override sent value: ${body.strict_schema_override}`).toBe(true);
    });
  });
});
