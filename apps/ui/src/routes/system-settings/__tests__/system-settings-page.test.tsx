/**
 * SystemSettingsPage —— /settings 5 tab + ApiKey masked + KeyringFallbackBanner +
 *                        Classifier test connection + SSRF + Wave3 strict_schema_override
 *
 * Traces To 特性 22 design §Test Inventory 22-01 / 22-02 / 22-03 / 22-04 / 22-05 /
 *                   22-23 / 22-38 / 22-39 / 22-40 / 22-43 / 22-44 ·
 *           §Interface Contract A (useGeneralSettings / useUpdateGeneralSettings /
 *                   useTestConnection / useGeneralKeyringStatus / MaskedKeyInput /
 *                   KeyringFallbackBanner) ·
 *           §Design Alignment seq msg#1 / #2 / #3 / #4 / #5 ·
 *           §Visual Rendering Contract settings-vtabs / masked-key-input /
 *                   keyring-fallback-banner ·
 *           SRS FR-032 + NFR-008 + IFR-004 + IFR-006.
 *
 * Red 阶段：`apps/ui/src/routes/system-settings/index.tsx` 尚未实现 → ImportError FAIL。
 *
 * Rule 4 错误实现挑战：
 *   - 「PUT 响应未触发 GET 重新拉取」→ T22-01 masked 字段不会更新 FAIL
 *   - 「mutation cache 保留 plaintext」→ T22-02 / 22-44 DOM grep 命中 FAIL
 *   - 「降级时静默无 banner」→ T22-03 banner 节点缺失 FAIL
 *   - 「401 → ErrorBoundary 整页崩」→ T22-04 期望 result.error.status 暴露但页面仍可见 FAIL
 *   - 「私网 IP 静默接受」→ T22-38 期望 mutation error.status===400 FAIL
 *   - 「strict_schema_override 字段被丢」→ T22-39 控件状态丢失 FAIL
 *   - 「MaskedKeyInput 切换后 plaintext 残留」→ T22-40 DOM 仍含明文 FAIL
 *
 * Rule 5 测试层级：
 *   - 本文件全部为 [unit]（vitest + happy-dom，fetch 在测试边界处 mock；hook + page + 组件
 *     真实导入 SUT）。
 *   - 后端 IAPI-002 / IAPI-014 真实集成已由 F19 keyring real test
 *     (`tests/integration/test_f19_real_keyring.py`) + F23 production-app real test
 *     (`tests/integration/test_f23_real_rest_routes.py` R16/R35) 覆盖。
 *   - F22 自身 real test 落 `tests/integration/test_f22_real_settings_consumer.py`
 *     （另文件）。
 *
 * [unit] —— uses fetch mocks; integration via tests/integration/test_f22_real_*.py.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, fireEvent, waitFor } from "@testing-library/react";
import * as React from "react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// SUT —— 全部在 Green 阶段实现；Red 阶段这些 import 必失败。
import { SystemSettingsPage } from "@/routes/system-settings";
import { MaskedKeyInput } from "@/routes/system-settings/components/masked-key-input";
import { KeyringFallbackBanner } from "@/routes/system-settings/components/keyring-fallback-banner";

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

const NATIVE_GENERAL = {
  api_key_ref: { service: "harness-classifier", user: "default" },
  api_key_masked: "***old",
  keyring_backend: "native" as const,
};

const FALLBACK_GENERAL = {
  api_key_ref: null,
  api_key_masked: null,
  keyring_backend: "keyrings.alt" as const,
};

function makeFetchSequence(responses: Array<{ status: number; body: unknown }>): ReturnType<typeof vi.fn> {
  const fn = vi.fn();
  for (const r of responses) {
    fn.mockResolvedValueOnce(
      new Response(JSON.stringify(r.body), {
        status: r.status,
        headers: { "Content-Type": "application/json" },
      }),
    );
  }
  return fn;
}

// ---------------------------------------------------------------------------
// 22-01 FUNC/happy — Update general settings → masked field renders ***abc
// Traces To FR-032 AC + §IC useUpdateGeneralSettings + §Design Alignment seq msg#1-#5
// ---------------------------------------------------------------------------
describe("22-01 FUNC/happy useUpdateGeneralSettings round-trip", () => {
  it("提交 plaintext → PUT /api/settings/general → masked '***abc' 渲染", async () => {
    const fetchMock = makeFetchSequence([
      { status: 200, body: NATIVE_GENERAL }, // initial GET
      {
        status: 200,
        body: {
          api_key_ref: { service: "harness-classifier", user: "default" },
          api_key_masked: "***abc",
          keyring_backend: "native",
        },
      }, // PUT
      {
        status: 200,
        body: {
          api_key_ref: { service: "harness-classifier", user: "default" },
          api_key_masked: "***abc",
          keyring_backend: "native",
        },
      }, // GET refetch
    ]);
    globalThis.fetch = fetchMock;
    const { container } = render(<SystemSettingsPage />, { wrapper: Wrapper });
    // 进入 ApiKey tab
    await waitFor(() => {
      const tab = container.querySelector('[data-component="settings-vtabs"] [data-tab-id="apikey"]');
      expect(tab).not.toBeNull();
    });
    fireEvent.click(
      container.querySelector('[data-component="settings-vtabs"] [data-tab-id="apikey"]') as Element,
    );
    // 点击「更换」展开输入框
    const changeBtn = await waitFor(() => {
      const b = container.querySelector('[data-testid="masked-key-change-btn"]');
      expect(b).not.toBeNull();
      return b as Element;
    });
    fireEvent.click(changeBtn);
    const input = container.querySelector('[data-testid="masked-key-plaintext-input"]') as HTMLInputElement;
    expect(input).not.toBeNull();
    fireEvent.change(input, { target: { value: "sk-test-12345abc" } });
    fireEvent.click(container.querySelector('[data-testid="masked-key-submit-btn"]') as Element);
    // 等 PUT 落定 → 重新拉 GET → masked 变为 ***abc
    await waitFor(() => {
      const masked = container.querySelector('[data-component="masked-key-input"]');
      expect(masked?.textContent ?? "").toMatch(/\*\*\*abc/);
    });
    const calls = (fetchMock.mock.calls as unknown[][]).map((c) => ({
      url: String(c[0]),
      method: String((c[1] as RequestInit | undefined)?.method ?? "GET"),
    }));
    expect(calls.some((c) => c.url.endsWith("/api/settings/general") && c.method === "PUT")).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 22-02 SEC/dom-scan — plaintext NEVER appears in DOM after submit
// Traces To FR-032 SEC + NFR-008 + §VRC MaskedKeyInput
// ---------------------------------------------------------------------------
describe("22-02 SEC/dom-scan plaintext 不残留 DOM", () => {
  it("提交 sk-supersecret-xyz 后 document.body.outerHTML / value / data-* / aria-* 全部 grep 0 命中", async () => {
    const PLAINTEXT = "sk-supersecret-xyz";
    const fetchMock = makeFetchSequence([
      { status: 200, body: NATIVE_GENERAL },
      {
        status: 200,
        body: {
          api_key_ref: { service: "harness-classifier", user: "default" },
          api_key_masked: "***xyz",
          keyring_backend: "native",
        },
      },
      {
        status: 200,
        body: {
          api_key_ref: { service: "harness-classifier", user: "default" },
          api_key_masked: "***xyz",
          keyring_backend: "native",
        },
      },
    ]);
    globalThis.fetch = fetchMock;
    const { container, baseElement } = render(<SystemSettingsPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(container.querySelector('[data-component="settings-vtabs"]')).not.toBeNull();
    });
    fireEvent.click(
      container.querySelector('[data-component="settings-vtabs"] [data-tab-id="apikey"]') as Element,
    );
    const changeBtn = await waitFor(() => {
      const b = container.querySelector('[data-testid="masked-key-change-btn"]');
      expect(b).not.toBeNull();
      return b as Element;
    });
    fireEvent.click(changeBtn);
    const input = container.querySelector('[data-testid="masked-key-plaintext-input"]') as HTMLInputElement;
    fireEvent.change(input, { target: { value: PLAINTEXT } });
    fireEvent.click(container.querySelector('[data-testid="masked-key-submit-btn"]') as Element);
    // 等 mutation 落定后扫描全 DOM
    await waitFor(() => {
      expect(container.querySelector('[data-component="masked-key-input"]')?.textContent ?? "").toMatch(
        /\*\*\*xyz/,
      );
    });
    // 1. outerHTML 不含 plaintext
    expect(baseElement.outerHTML.includes(PLAINTEXT)).toBe(false);
    // 2. 任何 input.value 不含 plaintext
    const inputs = baseElement.querySelectorAll("input");
    for (const i of Array.from(inputs)) {
      expect((i as HTMLInputElement).value.includes(PLAINTEXT)).toBe(false);
    }
    // 3. 任何 textarea.value 不含 plaintext
    const textareas = baseElement.querySelectorAll("textarea");
    for (const t of Array.from(textareas)) {
      expect((t as HTMLTextAreaElement).value.includes(PLAINTEXT)).toBe(false);
    }
    // 4. data-* / aria-* 属性扫描
    const allEls = baseElement.querySelectorAll("*");
    for (const el of Array.from(allEls)) {
      for (const attr of Array.from(el.attributes)) {
        if (attr.name.startsWith("data-") || attr.name.startsWith("aria-")) {
          expect(attr.value.includes(PLAINTEXT)).toBe(false);
        }
      }
    }
  });
});

// ---------------------------------------------------------------------------
// 22-03 SEC/keyring-fallback — banner renders when backend != 'native'
// Traces To IFR-006 + §VRC KeyringFallbackBanner
// ---------------------------------------------------------------------------
describe("22-03 SEC/keyring-fallback banner 渲染", () => {
  it("/api/settings/general 返回 keyring_backend='keyrings.alt' → banner 可见 + aria-label='Keyring 降级告警'", async () => {
    globalThis.fetch = makeFetchSequence([{ status: 200, body: FALLBACK_GENERAL }]);
    const { container } = render(<SystemSettingsPage />, { wrapper: Wrapper });
    await waitFor(() => {
      const banner = container.querySelector('[data-testid="keyring-fallback-banner"]');
      expect(banner).not.toBeNull();
      expect(banner?.getAttribute("aria-label")).toBe("Keyring 降级告警");
    });
  });

  it("backend=='native' 时 banner 不渲染（component 单元）", () => {
    const { container } = render(<KeyringFallbackBanner backend="native" />);
    expect(container.querySelector('[data-testid="keyring-fallback-banner"]')).toBeNull();
  });

  it("backend=='fail' 时 banner 渲染 + 错误样式 data-state='fail'", () => {
    const { container } = render(<KeyringFallbackBanner backend="fail" />);
    const banner = container.querySelector('[data-testid="keyring-fallback-banner"]');
    expect(banner).not.toBeNull();
    expect(banner?.getAttribute("data-state")).toBe("fail");
  });
});

// ---------------------------------------------------------------------------
// 22-04 FUNC/error — useTestConnection 401 → mapped HttpError 400
// Traces To FR-032 + IFR-004 + §IC useTestConnection Raises 401
// ---------------------------------------------------------------------------
describe("22-04 FUNC/error useTestConnection 401 映射 400", () => {
  it("POST /api/settings/classifier/test 返 401 → 路由层 400 → UI 横幅 + 不阻塞 Save", async () => {
    const fetchMock = makeFetchSequence([
      { status: 200, body: NATIVE_GENERAL },
      { status: 400, body: { detail: { code: "invalid_api_key", message: "401 unauthorized" } } },
    ]);
    globalThis.fetch = fetchMock;
    const { container } = render(<SystemSettingsPage />, { wrapper: Wrapper });
    await waitFor(() =>
      expect(container.querySelector('[data-component="settings-vtabs"]')).not.toBeNull(),
    );
    fireEvent.click(
      container.querySelector('[data-component="settings-vtabs"] [data-tab-id="classifier"]') as Element,
    );
    const testBtn = await waitFor(() => {
      const b = container.querySelector('[data-testid="classifier-test-connection-btn"]');
      expect(b).not.toBeNull();
      return b as Element;
    });
    fireEvent.click(testBtn);
    await waitFor(() => {
      const banner = container.querySelector('[data-testid="test-connection-error-banner"]');
      expect(banner).not.toBeNull();
      expect(banner?.textContent ?? "").toMatch(/invalid_api_key|unauthorized/);
    });
    // Save button 不被阻塞
    const saveBtn = container.querySelector('[data-testid="classifier-save-btn"]') as HTMLButtonElement | null;
    expect(saveBtn?.disabled).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 22-05 FUNC/error — useTestConnection refused → 502 banner
// Traces To IFR-004 + §IC useTestConnection Raises 502
// ---------------------------------------------------------------------------
describe("22-05 FUNC/error useTestConnection 502 connection-refused", () => {
  it("POST /api/settings/classifier/test 返 502 → 横幅显示 '连接被拒绝' 不触发 ErrorBoundary 整页崩", async () => {
    const fetchMock = makeFetchSequence([
      { status: 200, body: NATIVE_GENERAL },
      { status: 502, body: { detail: "connection refused" } },
    ]);
    globalThis.fetch = fetchMock;
    const { container } = render(<SystemSettingsPage />, { wrapper: Wrapper });
    await waitFor(() =>
      expect(container.querySelector('[data-component="settings-vtabs"]')).not.toBeNull(),
    );
    fireEvent.click(
      container.querySelector('[data-component="settings-vtabs"] [data-tab-id="classifier"]') as Element,
    );
    const testBtn = await waitFor(() => {
      const b = container.querySelector('[data-testid="classifier-test-connection-btn"]');
      expect(b).not.toBeNull();
      return b as Element;
    });
    fireEvent.click(testBtn);
    await waitFor(() => {
      const banner = container.querySelector('[data-testid="test-connection-error-banner"]');
      expect(banner).not.toBeNull();
      expect(banner?.textContent ?? "").toMatch(/连接被拒绝|connection refused/);
    });
    // 整页未崩溃：vtabs 仍然可见
    expect(container.querySelector('[data-component="settings-vtabs"]')).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 22-23 UI/render — 5 vtabs + SettingsFormSection 卡片堆叠（vitest happy-dom 等价）
// Traces To §VRC SystemSettings vtabs（[devtools] 行延 ST 真浏览器）
// ---------------------------------------------------------------------------
describe("22-23 UI/render SystemSettings 5 vtabs + SettingsFormSection 卡片", () => {
  it("/settings 加载后 vtabs 节点数 === 5；右侧至少 1 个 settings-form-section", async () => {
    globalThis.fetch = makeFetchSequence([{ status: 200, body: NATIVE_GENERAL }]);
    const { container } = render(<SystemSettingsPage />, { wrapper: Wrapper });
    await waitFor(() => {
      const tabs = container.querySelectorAll('[data-component="settings-vtabs"] .vtab');
      expect(tabs.length).toBe(5);
      const sections = container.querySelectorAll('[data-component="settings-form-section"]');
      expect(sections.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("激活 tab 节点带 data-active='true'（左缘 accent 视觉用）", async () => {
    globalThis.fetch = makeFetchSequence([{ status: 200, body: NATIVE_GENERAL }]);
    const { container } = render(<SystemSettingsPage />, { wrapper: Wrapper });
    await waitFor(() => {
      const active = container.querySelector('[data-component="settings-vtabs"] .vtab[data-active="true"]');
      expect(active).not.toBeNull();
    });
  });
});

// ---------------------------------------------------------------------------
// 22-38 SEC/ssrf — base_url 169.254.169.254 → mutation error.status===400
// Traces To INT-016 + IFR-004 + §IC useUpdateClassifierConfig Raises 400
// ---------------------------------------------------------------------------
describe("22-38 SEC/ssrf 私网 IP 拒绝", () => {
  it("用户输入 base_url='http://169.254.169.254' → PUT 返 400 → 横幅显示 'private network'", async () => {
    const fetchMock = makeFetchSequence([
      { status: 200, body: NATIVE_GENERAL },
      { status: 400, body: { detail: { code: "ssrf_blocked", message: "private network address rejected" } } },
    ]);
    globalThis.fetch = fetchMock;
    const { container } = render(<SystemSettingsPage />, { wrapper: Wrapper });
    await waitFor(() =>
      expect(container.querySelector('[data-component="settings-vtabs"]')).not.toBeNull(),
    );
    fireEvent.click(
      container.querySelector('[data-component="settings-vtabs"] [data-tab-id="classifier"]') as Element,
    );
    const baseInput = await waitFor(() => {
      const i = container.querySelector('[data-testid="classifier-base-url-input"]');
      expect(i).not.toBeNull();
      return i as HTMLInputElement;
    });
    fireEvent.change(baseInput, { target: { value: "http://169.254.169.254" } });
    fireEvent.click(container.querySelector('[data-testid="classifier-save-btn"]') as Element);
    await waitFor(() => {
      const banner = container.querySelector('[data-testid="classifier-save-error-banner"]');
      expect(banner).not.toBeNull();
      expect(banner?.textContent ?? "").toMatch(/private network|ssrf_blocked/);
    });
  });
});

// ---------------------------------------------------------------------------
// 22-39 FUNC/happy — strict_schema_override 三态 round-trip（Wave 3）
// Traces To IFR-004 Wave 3 + §IC strict_schema_override
// ---------------------------------------------------------------------------
describe("22-39 FUNC/happy strict_schema_override 三态控件", () => {
  it("提交 strict_schema_override=false → 响应回填 → 控件状态正确", async () => {
    const fetchMock = makeFetchSequence([
      {
        status: 200,
        body: {
          ...NATIVE_GENERAL,
          classifier: {
            base_url: "https://api.example.com",
            preset: "openai",
            strict_schema_override: null,
            enabled: true,
          },
        },
      },
      {
        status: 200,
        body: {
          ...NATIVE_GENERAL,
          classifier: {
            base_url: "https://api.example.com",
            preset: "openai",
            strict_schema_override: false,
            enabled: true,
          },
        },
      },
      {
        status: 200,
        body: {
          ...NATIVE_GENERAL,
          classifier: {
            base_url: "https://api.example.com",
            preset: "openai",
            strict_schema_override: false,
            enabled: true,
          },
        },
      },
    ]);
    globalThis.fetch = fetchMock;
    const { container } = render(<SystemSettingsPage />, { wrapper: Wrapper });
    await waitFor(() =>
      expect(container.querySelector('[data-component="settings-vtabs"]')).not.toBeNull(),
    );
    fireEvent.click(
      container.querySelector('[data-component="settings-vtabs"] [data-tab-id="classifier"]') as Element,
    );
    const overrideFalse = await waitFor(() => {
      const r = container.querySelector('[data-testid="strict-schema-override-false"]');
      expect(r).not.toBeNull();
      return r as HTMLInputElement;
    });
    fireEvent.click(overrideFalse);
    fireEvent.click(container.querySelector('[data-testid="classifier-save-btn"]') as Element);
    await waitFor(() => {
      const radio = container.querySelector(
        '[data-testid="strict-schema-override-false"]',
      ) as HTMLInputElement | null;
      expect(radio?.checked).toBe(true);
    });
  });
});

// ---------------------------------------------------------------------------
// 22-40 UI/render — MaskedKeyInput 切换 + 提交后 plaintext draft 重置
// Traces To §IC <MaskedKeyInput> 切换 + 交互深度
// ---------------------------------------------------------------------------
describe("22-40 UI/render MaskedKeyInput 交互深度", () => {
  it("点击「更换」→ password input 出现；提交后 input.value 立即回到空字符串", () => {
    const onSubmit = vi.fn();
    const { container } = render(
      <MaskedKeyInput masked="***old" onSubmitPlaintext={onSubmit} />,
    );
    // 默认 readonly 显示
    expect(container.querySelector('[data-testid="masked-key-plaintext-input"]')).toBeNull();
    fireEvent.click(container.querySelector('[data-testid="masked-key-change-btn"]') as Element);
    const input = container.querySelector('[data-testid="masked-key-plaintext-input"]') as HTMLInputElement;
    expect(input).not.toBeNull();
    expect(input.type).toBe("password");
    fireEvent.change(input, { target: { value: "sk-fresh-456" } });
    expect(input.value).toBe("sk-fresh-456");
    fireEvent.click(container.querySelector('[data-testid="masked-key-submit-btn"]') as Element);
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith("sk-fresh-456");
    // 提交后内部 state 重置 → 重新展开输入框，value 应为空
    fireEvent.click(container.querySelector('[data-testid="masked-key-change-btn"]') as Element);
    const reopened = container.querySelector(
      '[data-testid="masked-key-plaintext-input"]',
    ) as HTMLInputElement | null;
    expect(reopened).not.toBeNull();
    expect(reopened?.value).toBe("");
  });

  it("masked=null → 显示「未配置」占位且不显示「更换」按钮", () => {
    const { container } = render(
      <MaskedKeyInput masked={null} onSubmitPlaintext={() => undefined} />,
    );
    expect(container.textContent ?? "").toContain("未配置");
    expect(container.querySelector('[data-testid="masked-key-change-btn"]')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 22-43 SEC/dom-scan — initial GET response never carries plaintext
// Traces To NFR-008 二次保险 + §IC useGeneralSettings GET
// ---------------------------------------------------------------------------
describe("22-43 SEC/dom-scan GET /api/settings/general 不带明文", () => {
  it("初次加载后 DOM 仅含 masked + ref 字段，没有 plaintext substring", async () => {
    const fetchMock = makeFetchSequence([{ status: 200, body: NATIVE_GENERAL }]);
    globalThis.fetch = fetchMock;
    const { container, baseElement } = render(<SystemSettingsPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(container.querySelector('[data-component="settings-vtabs"]')).not.toBeNull();
      // Wait until the GET /api/settings/general response has flowed through
      // so the masked summary (`***old`) is materialised in the rendered DOM.
      expect(baseElement.outerHTML.includes("***old")).toBe(true);
    });
    // 任何疑似 plaintext 模式 sk-xxx 都不应在 DOM
    const html = baseElement.outerHTML;
    expect(/sk-[a-zA-Z0-9]{8,}/.test(html)).toBe(false);
    // 但 masked 节点应有 ***old
    expect(html.includes("***old")).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 22-44 SEC/audit-log-scan — plaintext only in PUT request body, never in console / localStorage
// Traces To NFR-008 + §IC useUpdateGeneralSettings
// ---------------------------------------------------------------------------
describe("22-44 SEC/audit-log-scan plaintext 只出现在请求体", () => {
  it("submit 后仅 PUT body 含 plaintext；console / localStorage / 后续 GET 响应均无", async () => {
    const PLAINTEXT = "sk-audit-xyz123";
    const consoleLogSpy = vi.spyOn(console, "log").mockImplementation(() => undefined);
    const consoleInfoSpy = vi.spyOn(console, "info").mockImplementation(() => undefined);
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const fetchMock = makeFetchSequence([
      { status: 200, body: NATIVE_GENERAL },
      {
        status: 200,
        body: {
          api_key_ref: { service: "harness-classifier", user: "default" },
          api_key_masked: "***123",
          keyring_backend: "native",
        },
      },
      {
        status: 200,
        body: {
          api_key_ref: { service: "harness-classifier", user: "default" },
          api_key_masked: "***123",
          keyring_backend: "native",
        },
      },
    ]);
    globalThis.fetch = fetchMock;
    const { container } = render(<SystemSettingsPage />, { wrapper: Wrapper });
    await waitFor(() =>
      expect(container.querySelector('[data-component="settings-vtabs"]')).not.toBeNull(),
    );
    fireEvent.click(
      container.querySelector('[data-component="settings-vtabs"] [data-tab-id="apikey"]') as Element,
    );
    fireEvent.click(
      (await waitFor(() => container.querySelector('[data-testid="masked-key-change-btn"]'))) as Element,
    );
    const input = container.querySelector('[data-testid="masked-key-plaintext-input"]') as HTMLInputElement;
    fireEvent.change(input, { target: { value: PLAINTEXT } });
    fireEvent.click(container.querySelector('[data-testid="masked-key-submit-btn"]') as Element);
    await waitFor(() => {
      expect(container.querySelector('[data-component="masked-key-input"]')?.textContent ?? "").toMatch(
        /\*\*\*123/,
      );
    });
    // PUT 请求体必须含 plaintext（业务必要）
    const putCall = (fetchMock.mock.calls as unknown[][]).find(
      (c) => String(c[0]).endsWith("/api/settings/general") && (c[1] as RequestInit | undefined)?.method === "PUT",
    );
    expect(putCall).not.toBeUndefined();
    const putBody = (putCall?.[1] as RequestInit | undefined)?.body as string;
    expect(putBody.includes(PLAINTEXT)).toBe(true);
    // 但 console 日志 / localStorage 无 plaintext
    const allLogs = [
      ...consoleLogSpy.mock.calls.flat(),
      ...consoleInfoSpy.mock.calls.flat(),
      ...consoleErrorSpy.mock.calls.flat(),
    ]
      .map((x) => (typeof x === "string" ? x : JSON.stringify(x)))
      .join(" ");
    expect(allLogs.includes(PLAINTEXT)).toBe(false);
    if (typeof globalThis.localStorage !== "undefined") {
      let lsBlob = "";
      for (let i = 0; i < globalThis.localStorage.length; i++) {
        const k = globalThis.localStorage.key(i);
        if (k) lsBlob += `${k}=${globalThis.localStorage.getItem(k)};`;
      }
      expect(lsBlob.includes(PLAINTEXT)).toBe(false);
    }
  });
});
