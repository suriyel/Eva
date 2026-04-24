/**
 * PageFrame — Sidebar + top bar + children wrapper.
 * Traces §VRC AppShell / Sidebar / Top bar.
 */
import * as React from "react";
import { Sidebar, type NavId } from "./sidebar";
import { Icons } from "./icons";

export interface PageFrameProps {
  active: NavId;
  title: string;
  hilCount?: number;
  children?: React.ReactNode;
  subtitle?: React.ReactNode;
  headerRight?: React.ReactNode;
  actions?: React.ReactNode;
  onNavigate?: (id: NavId) => void;
}

export function PageFrame({
  active,
  title,
  hilCount = 0,
  children,
  subtitle,
  headerRight,
  actions,
  onNavigate,
}: PageFrameProps): React.ReactElement {
  if (!title) {
    // non-empty precondition per §IC
    throw new TypeError("PageFrame.title must be non-empty");
  }
  return (
    <div
      className="hns"
      style={{
        display: "flex",
        height: "100%",
        width: "100%",
        overflow: "hidden",
        background: "var(--bg-app)",
      }}
    >
      <Sidebar active={active} hilCount={hilCount} onNavigate={onNavigate} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <header
          data-component="top-bar"
          style={{
            height: "56px",
            padding: "0 24px",
            display: "flex",
            alignItems: "center",
            gap: 16,
            borderBottom: "1px solid var(--border-subtle)",
            background:
              "linear-gradient(180deg, var(--bg-surface) 0%, var(--bg-app) 100%)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
            <div style={{ fontSize: 20, fontWeight: 600 }}>{title}</div>
            {subtitle}
          </div>
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
            {headerRight}
            <div
              style={{
                width: 220,
                display: "flex",
                alignItems: "center",
                gap: 8,
                height: 30,
                padding: "0 12px",
                borderRadius: 4,
                background: "var(--bg-surface)",
                border: "1px solid var(--border)",
                color: "var(--fg-dim)",
              }}
            >
              <Icons.Search size={13} />
              <span style={{ fontSize: 12.5, flex: 1 }}>跳转…</span>
              <kbd style={{ fontSize: 10.5 }}>⌘K</kbd>
            </div>
            {actions}
          </div>
        </header>
        <div style={{ flex: 1, overflow: "auto", minHeight: 0 }}>{children}</div>
      </div>
    </div>
  );
}
