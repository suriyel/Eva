/**
 * KeyringFallbackBanner — F22 §IC Section A.
 * Renders when the production keyring backend is not native (IFR-006).
 */
import * as React from "react";

export interface KeyringFallbackBannerProps {
  backend: "native" | "keyrings.alt" | "fail";
}

export function KeyringFallbackBanner(
  props: KeyringFallbackBannerProps,
): React.ReactElement | null {
  const { backend } = props;
  if (backend === "native") return null;
  return (
    <div
      data-testid="keyring-fallback-banner"
      data-state={backend === "fail" ? "fail" : "warning"}
      aria-label="Keyring 降级告警"
      role="status"
      style={{
        padding: 8,
        background:
          backend === "fail" ? "var(--state-fail, #fee)" : "var(--state-warn, #fff7e6)",
      }}
    >
      {backend === "fail"
        ? "Keyring 不可用：API key 暂存于明文文件后端，请尽快配置原生 keyring。"
        : "Keyring 降级到 keyrings.alt 文件后端。"}
    </div>
  );
}
