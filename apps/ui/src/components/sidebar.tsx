/**
 * Sidebar — 8 nav items + HIL badge + responsive collapse + v1.0.0 chip +
 * 当前 Run selector + Runtime status card + a11y labels (F24 B7).
 * Traces §VRC Sidebar 展开 / 折叠 / 激活项 / HIL 徽标 · §BC viewport 1279 ·
 *        §IS B7 (version chip / current run / runtime card / a11y).
 */
import * as React from "react";
import { useQuery, QueryClientContext } from "@tanstack/react-query";
import { Icons } from "./icons";
import { resolveApiBaseUrl } from "../api/client";
import { WorkdirPicker } from "./workdir-picker";

const APP_VERSION = "v1.0.0";

interface HealthShape {
  bind?: string;
  version?: string;
  cli_versions?: { claude?: string | null; opencode?: string | null };
}

interface CurrentRunShape {
  run_id: string;
  state?: string;
}

/** Detect QueryClient availability without throwing — sidebar gracefully
 * degrades when used in test wrappers that don't supply a provider
 * (e.g. legacy F12 PageFrame tests). */
function useHasQueryClient(): boolean {
  const client = React.useContext(QueryClientContext);
  return client !== undefined;
}

/** A safe useQuery that no-ops when no QueryClientProvider is present. */
function useSafeQuery<T>(opts: {
  queryKey: unknown[];
  fetcher: () => Promise<T | null>;
}): T | null {
  const hasClient = useHasQueryClient();
  if (hasClient) {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    return useQueryInternal<T>(opts);
  }
  return null;
}

function useQueryInternal<T>(opts: {
  queryKey: unknown[];
  fetcher: () => Promise<T | null>;
}): T | null {
  const q = useQuery<T | null>({
    queryKey: opts.queryKey,
    retry: false,
    queryFn: async () => opts.fetcher(),
  });
  return q.data ?? null;
}

function useHealthForSidebar(): HealthShape | null {
  return useSafeQuery<HealthShape>({
    queryKey: ["GET", "/api/health"],
    fetcher: async () => {
      const resp = await fetch(`${resolveApiBaseUrl()}/api/health`);
      if (!resp.ok) return null;
      const text = await resp.text();
      return text ? (JSON.parse(text) as HealthShape) : null;
    },
  });
}

function useCurrentRunForSidebar(): CurrentRunShape | null {
  return useSafeQuery<CurrentRunShape>({
    queryKey: ["GET", "/api/runs/current"],
    fetcher: async () => {
      const resp = await fetch(`${resolveApiBaseUrl()}/api/runs/current`);
      if (resp.status === 404) return null;
      if (!resp.ok) return null;
      const text = await resp.text();
      if (!text || text === "null") return null;
      return JSON.parse(text) as CurrentRunShape;
    },
  });
}

export type NavId =
  | "overview"
  | "hil"
  | "stream"
  | "docs"
  | "process"
  | "commits"
  | "skills"
  | "settings";

type IconElement = (typeof Icons)[string];

interface NavItem {
  id: NavId;
  label: string;
  icon: IconElement;
}

const NAV_ITEMS: NavItem[] = [
  { id: "overview", label: "总览", icon: Icons.Home },
  { id: "hil", label: "HIL 待答", icon: Icons.Inbox },
  { id: "stream", label: "Ticket 流", icon: Icons.Zap },
  { id: "docs", label: "文档 & ROI", icon: Icons.FileText },
  { id: "process", label: "过程文件", icon: Icons.Edit3 },
  { id: "commits", label: "提交历史", icon: Icons.GitBranch },
  { id: "skills", label: "提示词 & 技能", icon: Icons.Book },
  { id: "settings", label: "设置", icon: Icons.Settings },
];

export interface SidebarProps {
  active: NavId;
  hilCount?: number;
  onNavigate?: (id: NavId) => void;
}

function useViewportWidth(): number {
  const [w, setW] = React.useState<number>(() =>
    typeof window !== "undefined" ? window.innerWidth : 1280,
  );
  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const onResize = (): void => setW(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return w;
}

export function Sidebar({ active, hilCount = 0, onNavigate }: SidebarProps): React.ReactElement {
  const width = useViewportWidth();
  const collapsed = width < 1280;
  const sidebarWidth = collapsed ? 56 : 240;
  const health = useHealthForSidebar();
  const currentRun = useCurrentRunForSidebar();
  const onlineState =
    health?.cli_versions && (health.cli_versions.claude || health.cli_versions.opencode)
      ? "online"
      : "offline";
  const claudeShort = health?.cli_versions?.claude ? "claude" : null;
  const opencodeShort = health?.cli_versions?.opencode ? "opencode" : null;
  const cliText = [claudeShort, opencodeShort].filter(Boolean).join(" · ") || "claude · opencode";

  return (
    <aside
      data-component="sidebar"
      data-collapsed={collapsed ? "true" : "false"}
      style={{
        width: `${sidebarWidth}px`,
        height: "100%",
        background: "var(--bg-surface)",
        borderRight: "1px solid var(--border-subtle)",
        display: "flex",
        flexDirection: "column",
        flex: "none",
      }}
    >
      <div
        style={{
          height: 56,
          padding: "0 16px",
          display: "flex",
          alignItems: "center",
          gap: 10,
          borderBottom: "1px solid var(--border-subtle)",
        }}
      >
        <div
          style={{
            width: 24,
            height: 24,
            borderRadius: 6,
            background: "linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%)",
            display: "grid",
            placeItems: "center",
            boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.15)",
            flex: "none",
          }}
        >
          <div
            style={{
              width: 10,
              height: 10,
              border: "1.5px solid #0A0D12",
              borderRadius: 2,
              transform: "rotate(45deg)",
            }}
          />
        </div>
        {!collapsed && (
          <>
            <div style={{ fontSize: 15, fontWeight: 600, letterSpacing: "-0.01em" }}>Harness</div>
            <code
              data-testid="version-chip"
              className="code-sm"
              style={{
                marginLeft: "auto",
                fontSize: 11,
                padding: "1px 6px",
                borderRadius: 4,
                background: "var(--bg-active)",
                color: "var(--fg-dim)",
                fontFamily: "var(--font-mono)",
              }}
            >
              {APP_VERSION}
            </code>
          </>
        )}
      </div>

      <WorkdirPicker collapsed={collapsed} />

      {!collapsed && currentRun?.run_id && (
        <div
          data-testid="current-run-selector"
          style={{
            padding: "8px 16px",
            borderBottom: "1px solid var(--border-subtle)",
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          <div style={{ fontSize: 11, color: "var(--fg-mute)" }}>当前 Run</div>
          <button
            type="button"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 8px",
              height: 36,
              borderRadius: 4,
              background: "var(--bg-app)",
              border: "1px solid var(--border-subtle)",
              color: "var(--fg)",
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            <span
              className="state-dot pulse"
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background:
                  currentRun?.state === "running" ? "var(--state-running)" : "var(--fg-mute)",
              }}
            />
            <code className="mono" style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
              {currentRun.run_id}
            </code>
            <Icons.ChevronDown size={14} />
          </button>
        </div>
      )}

      <nav style={{ padding: 8, flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
        {NAV_ITEMS.map((it) => {
          const isActive = it.id === active;
          const IconEl = it.icon;
          return (
            <div
              key={it.id}
              data-nav={it.id}
              data-testid={`nav-${it.id}`}
              data-active={isActive ? "true" : "false"}
              role="button"
              tabIndex={0}
              title={it.label}
              aria-label={it.label}
              onClick={() => onNavigate?.(it.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onNavigate?.(it.id);
                }
              }}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                height: 36,
                padding: "0 12px",
                borderRadius: 6,
                color: isActive ? "var(--fg)" : "var(--fg-dim)",
                fontSize: 13,
                fontWeight: 500,
                cursor: "pointer",
                position: "relative",
                background: isActive ? "var(--bg-active)" : "transparent",
              }}
            >
              {isActive && (
                <div
                  style={{
                    position: "absolute",
                    left: -8,
                    top: 8,
                    bottom: 8,
                    width: 3,
                    borderRadius: 2,
                    background: "var(--accent)",
                  }}
                />
              )}
              <IconEl size={16} />
              {!collapsed && <span>{it.label}</span>}
              {it.id === "hil" && hilCount > 0 && (
                <span
                  data-badge="true"
                  style={{
                    marginLeft: "auto",
                    minWidth: 18,
                    height: 18,
                    padding: "0 5px",
                    borderRadius: 9,
                    background: "var(--state-hil)",
                    color: "#15100A",
                    fontSize: 10.5,
                    fontWeight: 700,
                    display: "grid",
                    placeItems: "center",
                  }}
                >
                  {hilCount}
                </span>
              )}
            </div>
          );
        })}
      </nav>

      {!collapsed && (
        <div
          data-testid="runtime-status-card"
          style={{
            margin: 12,
            padding: "8px 12px",
            borderRadius: 6,
            background: "var(--bg-app)",
            border: "1px solid var(--border-subtle)",
            display: "flex",
            alignItems: "center",
            gap: 8,
            height: 56,
          }}
        >
          <span
            className="state-dot"
            data-state={onlineState}
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background:
                onlineState === "online" ? "var(--state-running)" : "var(--state-fail)",
            }}
          />
          <div style={{ display: "flex", flexDirection: "column", gap: 2, flex: 1 }}>
            <div style={{ fontSize: 12, fontWeight: 500, color: "var(--fg)" }}>
              Runtime · {onlineState === "online" ? "在线" : "离线"}
            </div>
            <code
              className="code-sm"
              style={{ fontSize: 11, color: "var(--fg-dim)", fontFamily: "var(--font-mono)" }}
            >
              {cliText}
            </code>
          </div>
          <Icons.Power size={14} />
        </div>
      )}
    </aside>
  );
}
