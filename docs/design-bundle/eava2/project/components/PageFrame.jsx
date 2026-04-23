/* global Sidebar, Icons */

// PageFrame — app shell with sidebar + top chrome, inside an artboard
const PageFrame = ({ active, hilCount = 3, phase = "req", title, subtitle, actions, children, headerRight }) => {
  return (
    <div className="hns" style={{ display: "flex", height: "100%", width: "100%", overflow: "hidden", background: "var(--bg-app)", borderRadius: 10 }}>
      <Sidebar active={active} hilCount={hilCount} phase={phase}/>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {/* Top bar */}
        <div style={{
          height: 56, padding: "0 24px", display: "flex", alignItems: "center", gap: 16,
          borderBottom: "1px solid var(--border-subtle)",
          background: "linear-gradient(180deg, var(--bg-surface) 0%, var(--bg-app) 100%)"
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
            <div className="h1" style={{ fontSize: 20, fontWeight: 600 }}>{title}</div>
            {subtitle}
          </div>
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
            {headerRight}
            <div className="input" style={{ width: 220, display: "flex", alignItems: "center", gap: 8, height: 30 }}>
              <Icons.Search size={13} style={{ color: "var(--fg-mute)" }}/>
              <span style={{ color: "var(--fg-mute)", fontSize: 12.5, flex: 1 }}>跳转…</span>
              <kbd>⌘K</kbd>
            </div>
            {actions}
          </div>
        </div>
        <div style={{ flex: 1, overflow: "auto", minHeight: 0 }}>
          {children}
        </div>
      </div>
    </div>
  );
};

window.PageFrame = PageFrame;
