/* global Icons */
const STATE_MAP = {
  pending: { color: "var(--state-pending)", label: "待调度", pulse: false },
  running: { color: "var(--state-running)", label: "运行中", pulse: true },
  classifying: { color: "var(--state-classify)", label: "分类中", pulse: true },
  hil_waiting: { color: "var(--state-hil)", label: "等待回答", pulse: true },
  completed: { color: "var(--state-done)", label: "已完成", pulse: false },
  failed: { color: "var(--state-fail)", label: "失败", pulse: false },
  retrying: { color: "var(--state-retry)", label: "重试中", pulse: true },
  aborted: { color: "var(--state-fail)", label: "已中止", pulse: false },
};

const ToolTag = ({ tool }) => {
  const map = {
    claude: { label: "claude", color: "#D2A8FF" },
    opencode: { label: "opencode", color: "#7DDBD3" },
  };
  const t = map[tool] || map.claude;
  return (
    <span className="chip code" style={{ color: t.color, borderColor: "var(--border)", height: 18, fontSize: 10 }}>
      {t.label}
    </span>
  );
};

const TicketCard = ({
  id, skill, tool, state, status, events, variant = "compact", selected,
}) => {
  const s = STATE_MAP[state] || STATE_MAP.pending;
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12,
      padding: "12px 16px",
      background: selected ? "var(--bg-active)" : "var(--bg-surface)",
      borderBottom: "1px solid var(--border-subtle)",
      position: "relative", cursor: "pointer",
      minHeight: 64,
    }}>
      {selected && <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: s.color }}/>}
      <span
        className={`state-dot ${s.pulse ? "pulse" : ""}`}
        style={{ background: s.color, color: s.color, width: 8, height: 8 }}
      />
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 4 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="mono" style={{ fontSize: 11.5, color: "var(--fg-mute)" }}>{id}</span>
          <span style={{ fontSize: 13.5, fontWeight: 500, color: "var(--fg)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {skill || <span style={{ color: "var(--fg-mute)" }}>(no skill)</span>}
          </span>
          {tool && <ToolTag tool={tool}/>}
        </div>
        <div className="small" style={{ fontSize: 11.5, color: "var(--fg-dim)", display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ color: s.color }}>{s.label}</span>
          <span style={{ color: "var(--fg-faint)" }}>·</span>
          <span className="mono" style={{ fontSize: 11 }}>{status}</span>
          {events != null && (
            <>
              <span style={{ color: "var(--fg-faint)" }}>·</span>
              <span>{events} events</span>
            </>
          )}
        </div>
      </div>
      <Icons.Chevron size={14} style={{ color: "var(--fg-mute)" }}/>
    </div>
  );
};

window.TicketCard = TicketCard;
window.STATE_MAP = STATE_MAP;
