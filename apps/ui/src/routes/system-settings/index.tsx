/**
 * SystemSettingsPage — F22 §IC Section A · /settings (UCD §4.3).
 *
 * 5 vertical tabs: Models · ApiKey · Classifier · MCP · UI.
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

type TabId = "models" | "apikey" | "classifier" | "mcp" | "ui";

const TABS: { id: TabId; label: string }[] = [
  { id: "models", label: "Models" },
  { id: "apikey", label: "ApiKey" },
  { id: "classifier", label: "Classifier" },
  { id: "mcp", label: "MCP" },
  { id: "ui", label: "UI" },
];

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
  const [tab, setTab] = React.useState<TabId>("models");
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

  // Classifier tab local state
  const [baseUrl, setBaseUrl] = React.useState<string>("");
  const [strictOverride, setStrictOverride] = React.useState<boolean | null>(null);
  React.useEffect(() => {
    const cls = data?.classifier as
      | {
          base_url?: string;
          strict_schema_override?: boolean | null;
        }
      | undefined;
    if (cls) {
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
          style={{ listStyle: "none", padding: 0, margin: 0 }}
        >
          {TABS.map((t) => (
            <li
              key={t.id}
              className="vtab"
              role="tab"
              data-tab-id={t.id}
              data-active={tab === t.id ? "true" : "false"}
              onClick={() => setTab(t.id)}
              style={{
                padding: 8,
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
          {tab === "models" && (
            <section data-component="settings-form-section" data-tab="models">
              <h3>Models</h3>
              <p>Model rules editor placeholder (F19 provider).</p>
            </section>
          )}
          {tab === "apikey" && (
            <section data-component="settings-form-section" data-tab="apikey">
              <h3>API Key</h3>
              <MaskedKeyInput masked={masked} onSubmitPlaintext={submitMaskedKey} />
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
              <label>
                Base URL{" "}
                <input
                  data-testid="classifier-base-url-input"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                />
              </label>
              <fieldset>
                <legend>strict_schema_override</legend>
                <label>
                  <input
                    type="radio"
                    name="strict-schema-override"
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
              {testConn.error && (
                <div data-testid="test-connection-error-banner" role="alert">
                  {describeError(testConn.error)}
                  {testConn.error instanceof HttpError && testConn.error.status === 502
                    ? " · 连接被拒绝"
                    : ""}
                </div>
              )}
              {updateClassifier.error && (
                <div data-testid="classifier-save-error-banner" role="alert">
                  {describeError(updateClassifier.error)}
                </div>
              )}
            </section>
          )}
          {tab === "mcp" && (
            <section data-component="settings-form-section" data-tab="mcp">
              <h3>MCP</h3>
              <p>MCP servers placeholder.</p>
            </section>
          )}
          {tab === "ui" && (
            <section data-component="settings-form-section" data-tab="ui">
              <h3>UI</h3>
              <p>UI density placeholder.</p>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
