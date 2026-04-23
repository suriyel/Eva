/* global Icons */
const { Home, Inbox, Zap, FileText, Edit3, GitBranch, Book, Settings, Power } = Icons;

const Sidebar = ({ active = "home", hilCount = 3, phase = "req" }) => {
  const items = [
    { id: "home", icon: <Home/>, label: "总览", badge: null },
    { id: "hil", icon: <Inbox/>, label: "HIL 待答", badge: hilCount },
    { id: "stream", icon: <Zap/>, label: "Ticket 流", badge: null },
    { id: "docs", icon: <FileText/>, label: "文档 & ROI", badge: null },
    { id: "process", icon: <Edit3/>, label: "过程文件", badge: null },
    { id: "commits", icon: <GitBranch/>, label: "提交历史", badge: null },
    { id: "skills", icon: <Book/>, label: "Skills", badge: null },
    { id: "settings", icon: <Settings/>, label: "设置", badge: null },
  ];
  return (
    <aside style={{
      width: 240, height: "100%", background: "var(--bg-surface)",
      borderRight: "1px solid var(--border-subtle)",
      display: "flex", flexDirection: "column", flex: "none"
    }}>
      {/* Brand */}
      <div style={{ height: 56, padding: "0 16px", display: "flex", alignItems: "center", gap: 10, borderBottom: "1px solid var(--border-subtle)" }}>
        <div style={{
          width: 24, height: 24, borderRadius: 6,
          background: "linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%)",
          display: "grid", placeItems: "center", boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.15)"
        }}>
          <div style={{ width: 10, height: 10, border: "1.5px solid #0A0D12", borderRadius: 2, transform: "rotate(45deg)" }}/>
        </div>
        <div style={{ fontSize: 15, fontWeight: 600, letterSpacing: "-0.01em" }}>Harness</div>
        <div className="code-sm" style={{ marginLeft: "auto", color: "var(--fg-mute)", fontSize: 10.5 }}>v1.0.0</div>
      </div>

      {/* Run selector pinned below brand */}
      <div style={{ padding: "10px 12px", borderBottom: "1px solid var(--border-subtle)" }}>
        <div className="label" style={{ fontSize: 10, marginBottom: 6, paddingLeft: 4 }}>当前 Run</div>
        <button className="btn secondary" style={{ width: "100%", justifyContent: "space-between", height: 34 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
            <span className="state-dot pulse" style={{ color: "var(--state-running)", background: "var(--state-running)" }}/>
            <span className="mono" style={{ fontSize: 12, color: "var(--fg)", overflow: "hidden", textOverflow: "ellipsis" }}>run-26.04.21-001</span>
          </div>
          <Icons.ChevronDown size={12}/>
        </button>
      </div>

      {/* Nav */}
      <nav style={{ padding: 8, flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
        {items.map(it => (
          <div key={it.id} className={`nav-item ${active === it.id ? "active" : ""}`}>
            {it.icon}
            <span>{it.label}</span>
            {it.badge ? (
              <span style={{
                marginLeft: "auto", minWidth: 18, height: 18, padding: "0 5px",
                borderRadius: 9, background: "var(--state-hil)", color: "#15100A",
                fontSize: 10.5, fontWeight: 700, display: "grid", placeItems: "center"
              }}>{it.badge}</span>
            ) : null}
          </div>
        ))}
      </nav>

      {/* Runtime status */}
      <div style={{ padding: 12, borderTop: "1px solid var(--border-subtle)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", background: "var(--bg-inset)", borderRadius: 6, border: "1px solid var(--border-subtle)" }}>
          <span className="state-dot" style={{ background: "var(--state-running)" }}/>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 11.5, fontWeight: 500 }}>Runtime · 在线</div>
            <div className="code-sm" style={{ color: "var(--fg-mute)", fontSize: 10 }}>claude · opencode</div>
          </div>
          <Power size={13} style={{ color: "var(--fg-mute)" }}/>
        </div>
      </div>
    </aside>
  );
};

window.Sidebar = Sidebar;
