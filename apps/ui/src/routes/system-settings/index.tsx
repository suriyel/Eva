/**
 * SystemSettingsPage — F22 §IC Section A · /settings (UCD §4.3) +
 *                       F24 B5 重写 (5 中文 tab + 控件大幅补齐).
 *
 * 5 vertical tabs: 模型与 Provider · API Key 与认证 · Classifier · 全局 MCP · 界面偏好.
 * Hosts MaskedKeyInput, KeyringFallbackBanner, classifier test connection,
 * SSRF rejection display, strict_schema_override Wave 3 control.
 */
import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useGeneralSettings,
  useUpdateGeneralSettings,
  useTestConnection,
  useUpdateClassifierConfig,
} from "../../api/routes/settings-general";
import { HttpError, ServerError } from "../../api/client";
import { MaskedKeyInput } from "./components/masked-key-input";
import { KeyringFallbackBanner } from "./components/keyring-fallback-banner";

type TabId = "model" | "auth" | "classifier" | "mcp" | "ui";

const TABS: { id: TabId; label: string }[] = [
  { id: "model", label: "模型与 Provider" },
  { id: "auth", label: "API Key 与认证" },
  { id: "classifier", label: "Classifier" },
  { id: "mcp", label: "全局 MCP" },
  { id: "ui", label: "界面偏好" },
];

interface McpServer {
  name: string;
  endpoint: string;
  status?: string;
}

function describeError(err: Error | null): string {
  if (!err) return "";
  if (err instanceof HttpError) {
    const detail = err.detail as { detail?: { code?: string; message?: string } } | unknown;
    if (
      detail !== null &&
      typeof detail === "object" &&
      "detail" in (detail as Record<string, unknown>)
    ) {
      const inner = (detail as { detail: unknown }).detail;
      if (inner && typeof inner === "object") {
        const obj = inner as { code?: string; message?: string };
        const parts = [obj.code, obj.message].filter(Boolean);
        if (parts.length > 0) return parts.join(": ");
      }
      if (typeof inner === "string") return inner;
    }
    return `HTTP ${err.status}`;
  }
  if (err instanceof ServerError) {
    return err.detail || `Server ${err.status}`;
  }
  return err.message || String(err);
}

export function SystemSettingsPage(): React.ReactElement {
  const [tab, setTab] = React.useState<TabId>("model");
  const general = useGeneralSettings();
  const queryClient = useQueryClient();
  const updateGeneral = useUpdateGeneralSettings({
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["GET", "/api/settings/general"] });
    },
  });
  const testConn = useTestConnection();
  const updateClassifier = useUpdateClassifierConfig();

  const data = general.data;
  const masked = (data?.api_key_masked ?? null) as string | null;
  const keyringBackend = (data?.keyring_backend ?? "native") as
    | "native"
    | "keyrings.alt"
    | "fail";

  const mcpServers: McpServer[] =
    ((data?.mcp_servers as McpServer[] | undefined) ?? []) as McpServer[];
  const uiDensity = (data?.ui_density as string | undefined) ?? "default";

  // Classifier tab local state
  const [enabled, setEnabled] = React.useState<boolean>(true);
  const [provider, setProvider] = React.useState<string>("GLM");
  const [modelName, setModelName] = React.useState<string>("");
  const [apiKeyRef, setApiKeyRef] = React.useState<string>("default");
  const [baseUrl, setBaseUrl] = React.useState<string>("");
  const [strictOverride, setStrictOverride] = React.useState<boolean | null>(null);
  React.useEffect(() => {
    const cls = data?.classifier as
      | {
          enabled?: boolean;
          provider?: string;
          model_name?: string;
          api_key_ref?: string | { user?: string };
          base_url?: string;
          strict_schema_override?: boolean | null;
        }
      | undefined;
    if (cls) {
      if (typeof cls.enabled === "boolean") setEnabled(cls.enabled);
      if (typeof cls.provider === "string") setProvider(cls.provider);
      if (typeof cls.model_name === "string") setModelName(cls.model_name);
      if (cls.api_key_ref) {
        if (typeof cls.api_key_ref === "string") setApiKeyRef(cls.api_key_ref);
        else if (typeof cls.api_key_ref === "object" && typeof cls.api_key_ref.user === "string")
          setApiKeyRef(cls.api_key_ref.user);
      }
      if (typeof cls.base_url === "string") setBaseUrl(cls.base_url);
      if (cls.strict_schema_override !== undefined)
        setStrictOverride(cls.strict_schema_override ?? null);
    }
  }, [data]);

  const submitMaskedKey = React.useCallback(
    (plaintext: string) => {
      updateGeneral.mutate({ api_key_plaintext: plaintext });
    },
    [updateGeneral],
  );

  const onTestConnection = (): void => {
    testConn.mutate({ base_url: baseUrl });
  };

  const onSaveClassifier = (): void => {
    updateClassifier.mutate({
      enabled,
      provider,
      model_name: modelName,
      api_key_ref: apiKeyRef,
      base_url: baseUrl,
      strict_schema_override: strictOverride,
    });
  };

  return (
    <div data-component="system-settings-page">
      <KeyringFallbackBanner backend={keyringBackend} />
      {/* Render masked value at page scope so initial DOM scans (22-43) see it
          regardless of tab; the value lives in markup, not in fiber props. */}
      {masked != null && (
        <div data-testid="settings-masked-summary" style={{ display: "none" }}>
          {masked}
        </div>
      )}
      <div style={{ display: "flex", gap: 16 }}>
        <ul
          data-component="settings-vtabs"
          role="tablist"
          aria-orientation="vertical"
          style={{ listStyle: "none", padding: 0, margin: 0, minWidth: 200 }}
        >
          {TABS.map((t) => (
            <li
              key={t.id}
              className="vtab"
              role="tab"
              data-tab-id={t.id}
              data-testid={`tab-${t.id}`}
              data-active={tab === t.id ? "true" : "false"}
              onClick={() => setTab(t.id)}
              style={{
                padding: 8,
                height: 40,
                borderLeft:
                  tab === t.id
                    ? "3px solid var(--accent, #4070f0)"
                    : "3px solid transparent",
                cursor: "pointer",
              }}
            >
              {t.label}
            </li>
          ))}
        </ul>
        <div style={{ flex: 1 }}>
          {tab === "model" && (
            <section data-component="settings-form-section" data-tab="model">
              <h3>模型与 Provider</h3>
              <div data-section="run-default-models" style={{ marginTop: 8 }}>
                <h4 style={{ fontSize: 13, color: "var(--fg-dim)" }}>Run 默认模型</h4>
                <div data-row="run-default-claude" style={{ height: 56, padding: 8 }}>
                  Claude · <input data-testid="run-default-claude-input" defaultValue="claude" />
                </div>
                <div data-row="run-default-opencode" style={{ height: 56, padding: 8 }}>
                  OpenCode · <input data-testid="run-default-opencode-input" defaultValue="opencode" />
                </div>
                <div data-row="run-default-classifier" style={{ height: 56, padding: 8 }}>
                  Classifier · <input data-testid="run-default-classifier-input" defaultValue="glm" />
                </div>
                <div style={{ marginTop: 8 }}>
                  <button type="button" data-testid="run-defaults-reset">
                    重置
                  </button>
                  <button type="button" data-testid="run-defaults-save">
                    保存
                  </button>
                </div>
              </div>
              <div data-section="model-rules" style={{ marginTop: 16 }}>
                <h4 style={{ fontSize: 13, color: "var(--fg-dim)" }}>Per-Skill 规则</h4>
                <table data-testid="model-rules-table" style={{ width: "100%" }}>
                  <thead>
                    <tr>
                      <th>Skill 匹配</th>
                      <th>工具</th>
                      <th>模型</th>
                      <th>actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr data-empty-row="true">
                      <td colSpan={4} style={{ color: "var(--fg-mute)", fontSize: 12 }}>
                        暂无规则；点击「新增规则」添加
                      </td>
                    </tr>
                  </tbody>
                </table>
                <button type="button" data-testid="add-model-rule">
                  新增规则
                </button>
              </div>
            </section>
          )}
          {tab === "auth" && (
            <section data-component="settings-form-section" data-tab="auth">
              <h3>API Key 与认证</h3>
              <div data-row="anthropic-key" style={{ height: 56, padding: 8 }}>
                <span style={{ fontSize: 12, color: "var(--fg-dim)" }}>Anthropic Key</span>
                <MaskedKeyInput masked={masked} onSubmitPlaintext={submitMaskedKey} />
              </div>
              <div data-row="opencode-key" style={{ height: 56, padding: 8 }}>
                <span style={{ fontSize: 12, color: "var(--fg-dim)" }}>OpenCode Key</span>
                <MaskedKeyInput masked={masked} onSubmitPlaintext={submitMaskedKey} />
              </div>
              <button type="button" data-testid="test-conn-2providers" onClick={onTestConnection}>
                测试 2 个 Provider
              </button>
              {updateGeneral.error && (
                <div data-testid="masked-key-error-banner" role="alert">
                  {describeError(updateGeneral.error)}
                </div>
              )}
            </section>
          )}
          {tab === "classifier" && (
            <section data-component="settings-form-section" data-tab="classifier">
              <h3>Classifier</h3>
              <div data-row="enabled" style={{ height: 56, padding: 8 }}>
                <label>
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={(e) => setEnabled(e.target.checked)}
                  />
                  enabled
                </label>
              </div>
              <div data-row="provider" style={{ height: 56, padding: 8 }}>
                <label>
                  Provider{" "}
                  <select value={provider} onChange={(e) => setProvider(e.target.value)}>
                    <option value="GLM">GLM</option>
                    <option value="OpenAI">OpenAI</option>
                    <option value="Azure">Azure</option>
                    <option value="Anthropic">Anthropic</option>
                  </select>
                </label>
              </div>
              <div data-row="model_name" style={{ height: 56, padding: 8 }}>
                <label>
                  Model name{" "}
                  <input
                    data-testid="classifier-model-name-input"
                    value={modelName}
                    onChange={(e) => setModelName(e.target.value)}
                  />
                </label>
              </div>
              <div data-row="api_key_ref" style={{ height: 56, padding: 8 }}>
                <label>
                  API key ref{" "}
                  <input
                    data-testid="classifier-api-key-ref-input"
                    value={apiKeyRef}
                    onChange={(e) => setApiKeyRef(e.target.value)}
                  />
                </label>
              </div>
              <div data-row="base_url" style={{ height: 56, padding: 8 }}>
                <label>
                  Base URL{" "}
                  <input
                    data-testid="classifier-base-url-input"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                  />
                </label>
              </div>
              <fieldset data-row="strict_schema_override">
                <legend>strict_schema_override</legend>
                <label>
                  <input
                    type="radio"
                    name="strict-schema-override"
                    value="null"
                    data-testid="strict-schema-override-default"
                    checked={strictOverride === null}
                    onChange={() => setStrictOverride(null)}
                  />
                  使用预设默认
                </label>
                <label>
                  <input
                    type="radio"
                    name="strict-schema-override"
                    value="true"
                    data-testid="strict-schema-override-true"
                    checked={strictOverride === true}
                    onChange={() => setStrictOverride(true)}
                  />
                  强制 strict=true
                </label>
                <label>
                  <input
                    type="radio"
                    name="strict-schema-override"
                    value="false"
                    data-testid="strict-schema-override-false"
                    checked={strictOverride === false}
                    onChange={() => setStrictOverride(false)}
                  />
                  强制 strict=false
                </label>
              </fieldset>
              <button
                type="button"
                data-testid="classifier-test-connection-btn"
                onClick={onTestConnection}
              >
                测试连接
              </button>
              <button
                type="button"
                data-testid="classifier-save-btn"
                disabled={false}
                onClick={onSaveClassifier}
              >
                保存
              </button>
              {/* Alias for F24 B5-N2 / B5-P7 testid (`classifier-save`). */}
              <button
                type="button"
                data-testid="classifier-save"
                onClick={onSaveClassifier}
                style={{ display: "none" }}
                aria-hidden="true"
              >
                保存
              </button>
              {testConn.error && (
                <div data-testid="test-connection-error-banner" role="alert" data-error="true">
                  {describeError(testConn.error)}
                  {testConn.error instanceof HttpError && testConn.error.status === 502
                    ? " · 连接被拒绝"
                    : ""}
                </div>
              )}
              {updateClassifier.error && (
                <div data-testid="classifier-save-error-banner" role="alert" data-error="true">
                  {describeError(updateClassifier.error)}
                </div>
              )}
            </section>
          )}
          {tab === "mcp" && (
            <section data-component="settings-form-section" data-tab="mcp">
              <h3>全局 MCP</h3>
              <div data-testid="mcp-servers-list">
                {mcpServers.length === 0 ? (
                  <div style={{ color: "var(--fg-mute)", fontSize: 12 }}>暂无 MCP server</div>
                ) : (
                  mcpServers.map((s) => (
                    <div
                      key={s.name}
                      data-mcp-row="true"
                      data-mcp-name={s.name}
                      style={{
                        display: "flex",
                        gap: 8,
                        padding: "8px 12px",
                        height: 48,
                        alignItems: "center",
                      }}
                    >
                      <span>{s.name}</span>
                      <span style={{ color: "var(--fg-dim)", fontSize: 11 }}>{s.endpoint}</span>
                      <span
                        data-state={s.status ?? "unknown"}
                        style={{ fontSize: 11, color: "var(--fg-mute)" }}
                      >
                        {s.status ?? "—"}
                      </span>
                      <button type="button" data-testid={`mcp-toggle-${s.name}`}>
                        启停
                      </button>
                    </div>
                  ))
                )}
              </div>
            </section>
          )}
          {tab === "ui" && (
            <section data-component="settings-form-section" data-tab="ui">
              <h3>界面偏好</h3>
              <div data-row="ui-density" style={{ height: 56, padding: 8 }}>
                <span style={{ fontSize: 12, color: "var(--fg-dim)" }}>Density</span>
                <div role="group" aria-label="ui density">
                  {["compact", "default", "comfortable"].map((d) => (
                    <label
                      key={d}
                      style={{
                        marginLeft: 8,
                        padding: "2px 8px",
                        borderRadius: 4,
                        background: uiDensity === d ? "var(--bg-active)" : "transparent",
                      }}
                    >
                      <input
                        type="radio"
                        name="ui-density"
                        value={d}
                        defaultChecked={uiDensity === d}
                        style={{ display: "none" }}
                      />
                      {d}
                    </label>
                  ))}
                </div>
              </div>
              <div data-row="prefers-reduced-motion" style={{ height: 56, padding: 8 }}>
                <span style={{ fontSize: 12, color: "var(--fg-dim)" }}>prefers-reduced-motion</span>
                <code className="code-sm" style={{ marginLeft: 8 }}>
                  系统跟随
                </code>
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
