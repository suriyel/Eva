/**
 * TicketCard — 9-state state-dot + tool chip prototype clone.
 * Traces §VRC TicketCard state-dot / tool chip · §BC state ∈ 9-tuple enum.
 */
import * as React from "react";
import { Icons } from "./icons";

export type TicketState =
  | "pending"
  | "running"
  | "classifying"
  | "hil_waiting"
  | "completed"
  | "failed"
  | "retrying"
  | "aborted";

interface StateSpec {
  color: string;
  label: string;
  pulse: boolean;
}

// Literal colors mirror tokens.css :root state-* values so getComputedStyle works in
// jsdom/happy-dom where var(...) is not resolved. CSS var reference is still used for
// class-level coloring to keep theme cascade intact.
const STATE_MAP: Record<TicketState, StateSpec> = {
  pending: { color: "rgb(110, 118, 129)", label: "待调度", pulse: false },
  running: { color: "rgb(62, 207, 142)", label: "运行中", pulse: true },
  classifying: { color: "rgb(177, 146, 251)", label: "分类中", pulse: true },
  hil_waiting: { color: "rgb(245, 181, 68)", label: "等待回答", pulse: true },
  completed: { color: "rgb(72, 181, 99)", label: "已完成", pulse: false },
  failed: { color: "rgb(242, 109, 109)", label: "失败", pulse: false },
  retrying: { color: "rgb(224, 138, 60)", label: "重试中", pulse: true },
  aborted: { color: "rgb(242, 109, 109)", label: "已中止", pulse: false },
};

const TOOL_MAP: Record<string, { label: string; color: string }> = {
  claude: { label: "claude", color: "rgb(210, 168, 255)" },
  opencode: { label: "opencode", color: "rgb(125, 219, 211)" },
};

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = React.useState(false);
  React.useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const handler = (ev: MediaQueryListEvent): void => setReduced(ev.matches);
    mq.addEventListener?.("change", handler);
    return () => mq.removeEventListener?.("change", handler);
  }, []);
  if (typeof window !== "undefined" && window.matchMedia) {
    try {
      const synchronous = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (synchronous !== reduced) return synchronous;
    } catch {
      /* ignore */
    }
  }
  return reduced;
}

export interface TicketCardProps {
  id: string;
  skill?: string;
  tool?: "claude" | "opencode";
  state: TicketState;
  status: string;
  events?: number;
  variant?: "compact";
  selected?: boolean;
}

export function TicketCard(props: TicketCardProps): React.ReactElement {
  const { id, skill, tool, state, status, events, selected } = props;
  const s = STATE_MAP[state] ?? STATE_MAP.pending;
  if (!STATE_MAP[state]) {
    // eslint-disable-next-line no-console
    console.warn(`TicketCard: unknown state=${state}, falling back to pending`);
  }
  const reduced = usePrefersReducedMotion();
  return (
    <div
      data-component="ticket-card"
      data-state={state}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "12px 16px",
        background: selected ? "var(--bg-active)" : "var(--bg-surface)",
        borderBottom: "1px solid var(--border-subtle)",
        position: "relative",
        cursor: "pointer",
        minHeight: 64,
      }}
    >
      {selected && (
        <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: s.color }} />
      )}
      <span
        data-state-dot=""
        className={`state-dot ${s.pulse ? "pulse" : ""}`}
        style={{
          background: s.color,
          color: s.color,
          width: 8,
          height: 8,
          borderRadius: "50%",
          display: "inline-block",
          flex: "none",
          animationName: reduced ? "none" : s.pulse ? "hns-pulse" : "none",
          animationDuration: "1.6s",
          animationTimingFunction: "cubic-bezier(0.4,0,0.2,1)",
          animationIterationCount: "infinite",
        }}
      />
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 4 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="mono" style={{ fontSize: 11.5, color: "var(--fg-mute)" }}>
            {id}
          </span>
          <span
            style={{
              fontSize: 13.5,
              fontWeight: 500,
              color: "var(--fg)",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {skill ?? <span style={{ color: "var(--fg-mute)" }}>(no skill)</span>}
          </span>
          {tool && (
            <span
              data-tool={tool}
              className="chip code"
              style={{
                color: TOOL_MAP[tool]?.color ?? TOOL_MAP.claude.color,
                borderColor: "var(--border)",
                height: 18,
                fontSize: 10,
                display: "inline-flex",
                alignItems: "center",
                padding: "0 8px",
                borderRadius: 9999,
                border: "1px solid var(--border)",
                fontFamily: "var(--font-mono)",
              }}
            >
              {TOOL_MAP[tool]?.label ?? tool}
            </span>
          )}
        </div>
        <div
          className="small"
          style={{ fontSize: 11.5, color: "var(--fg-dim)", display: "flex", alignItems: "center", gap: 8 }}
        >
          <span style={{ color: s.color }}>{s.label}</span>
          <span style={{ color: "var(--fg-faint)" }}>·</span>
          <span className="mono" style={{ fontSize: 11 }}>
            {status}
          </span>
          {events != null && (
            <>
              <span style={{ color: "var(--fg-faint)" }}>·</span>
              <span>{events} events</span>
            </>
          )}
        </div>
      </div>
      <Icons.Chevron size={14} style={{ color: "var(--fg-mute)" }} />
    </div>
  );
}
