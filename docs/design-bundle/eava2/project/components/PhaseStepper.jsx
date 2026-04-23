/* global Icons */
const PhaseStepper = ({ current = 0, fraction = null, variant = "h" }) => {
  const phases = [
    { id: "req", label: "需求", color: "var(--phase-req)" },
    { id: "ucd", label: "UCD", color: "var(--phase-ucd)" },
    { id: "design", label: "设计", color: "var(--phase-design)" },
    { id: "ats", label: "ATS", color: "var(--phase-ats)" },
    { id: "init", label: "初始化", color: "var(--phase-init)" },
    { id: "work", label: "开发", color: "var(--phase-work)" },
    { id: "st", label: "系统测试", color: "var(--phase-st)" },
    { id: "finalize", label: "归档", color: "var(--phase-finalize)" },
  ];

  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 0, padding: "8px 4px" }}>
      {phases.map((p, i) => {
        const state = i < current ? "done" : i === current ? "current" : "pending";
        return (
          <React.Fragment key={p.id}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, flex: "none", width: 84 }}>
              <div style={{
                position: "relative",
                width: 32, height: 32, borderRadius: "50%",
                background: state === "done" ? p.color : state === "current" ? p.color : "transparent",
                border: state === "pending" ? "1.5px solid var(--border)" : "none",
                display: "grid", placeItems: "center",
                boxShadow: state === "current" ? `0 0 0 4px ${p.color}22` : "none",
                transition: "all 180ms"
              }}>
                {state === "done" && <Icons.Check size={14} style={{ color: "#0A0D12" }}/>}
                {state === "current" && (
                  <>
                    <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#0A0D12" }}/>
                    <div style={{
                      position: "absolute", inset: -6, borderRadius: "50%",
                      border: `1.5px solid ${p.color}`, animation: "hns-pulse 1.8s ease-out infinite"
                    }}/>
                  </>
                )}
                {state === "pending" && (
                  <div style={{ width: 4, height: 4, borderRadius: "50%", background: "var(--fg-faint)" }}/>
                )}
              </div>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
                <div style={{
                  fontSize: 12, fontWeight: state === "current" ? 600 : 500,
                  color: state === "pending" ? "var(--fg-mute)" : "var(--fg)"
                }}>{p.label}</div>
                {i === current && fraction && (
                  <div className="mono" style={{ fontSize: 10.5, color: p.color }}>{fraction}</div>
                )}
              </div>
            </div>
            {i < phases.length - 1 && (
              <div style={{ flex: 1, height: 2, marginTop: 15, background: i < current ? p.color : "var(--border-subtle)", borderRadius: 1, opacity: i < current ? 0.6 : 1 }}/>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};

window.PhaseStepper = PhaseStepper;
