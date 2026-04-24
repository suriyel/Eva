/**
 * Sidebar — 8 nav items + HIL badge + responsive collapse.
 * Traces §VRC Sidebar 展开 / 折叠 / 激活项 / HIL 徽标 · §BC viewport 1279.
 */
import * as React from "react";
import { Icons } from "./icons";

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
  { id: "skills", label: "Skills", icon: Icons.Book },
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
          <div style={{ fontSize: 15, fontWeight: 600, letterSpacing: "-0.01em" }}>Harness</div>
        )}
      </div>

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
              onClick={() => onNavigate?.(it.id)}
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
    </aside>
  );
}
