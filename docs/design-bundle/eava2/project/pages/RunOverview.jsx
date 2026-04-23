/* global PageFrame, PhaseStepper, TicketCard, Icons, STATE_MAP */

const tickets = [
  { id: "#t-0042", skill: "long-task-requirements", tool: "claude", state: "running", status: "2m 14s", events: 32 },
  { id: "#t-0041", skill: "phase-router", tool: "claude", state: "completed", status: "11s", events: 4 },
  { id: "#t-0040", skill: "using-claude", tool: "claude", state: "completed", status: "6s", events: 3 },
  { id: "#t-0039", skill: "requirements-draft", tool: "opencode", state: "hil_waiting", status: "1m 02s", events: 18 },
  { id: "#t-0038", skill: "context-scanner", tool: "claude", state: "completed", status: "34s", events: 27 },
  { id: "#t-0037", skill: "pain-extractor", tool: "claude", state: "retrying", status: "3/5 · 12s", events: 9 },
  { id: "#t-0036", skill: "using-opencode", tool: "opencode", state: "completed", status: "8s", events: 5 },
  { id: "#t-0035", skill: "run-init", tool: "claude", state: "completed", status: "2s", events: 2 },
];

const Metric = ({ label, value, mono, color, icon }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 0", borderBottom: "1px solid var(--border-subtle)" }}>
    <div style={{ width: 24, color: "var(--fg-mute)" }}>{icon}</div>
    <div className="label" style={{ fontSize: 10.5, width: 84 }}>{label}</div>
    <div style={{ flex: 1, textAlign: "right", fontSize: 13.5, fontWeight: 500, color: color || "var(--fg)", fontFamily: mono ? "var(--font-mono)" : "inherit" }}>{value}</div>
  </div>
);

const EventLine = ({ type, text }) => {
  const typeMap = {
    tool_use: { color: "var(--accent-2)", bg: "rgba(177,146,251,0.12)", label: "tool_use" },
    tool_result: { color: "var(--accent-3)", bg: "rgba(125,219,211,0.12)", label: "tool_result" },
    text: { color: "var(--fg-dim)", bg: "var(--bg-inset)", label: "text" },
    thinking: { color: "var(--state-hil)", bg: "rgba(245,181,68,0.12)", label: "thinking" },
  };
  const t = typeMap[type] || typeMap.text;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 0" }}>
      <Icons.Chevron size={11} style={{ color: "var(--fg-faint)" }}/>
      <span style={{
        display: "inline-flex", alignItems: "center", padding: "2px 7px", borderRadius: 4,
        fontSize: 10, fontWeight: 600, letterSpacing: "0.02em",
        color: t.color, background: t.bg, fontFamily: "var(--font-mono)", flex: "none"
      }}>{t.label}</span>
      <span className="mono" style={{ fontSize: 12, color: "var(--fg-dim)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{text}</span>
    </div>
  );
};

const RunOverviewPage = () => (
  <PageFrame
    active="home"
    title="总览"
    subtitle={
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span className="chip code" style={{ color: "var(--accent-3)" }}>#run-26.04.21-001</span>
        <span className="chip solid" style={{ color: "var(--state-running)" }}>
          <span className="state-dot pulse" style={{ background: "var(--state-running)", color: "var(--state-running)", width: 6, height: 6 }}/>
          running · 14m 22s
        </span>
      </div>
    }
    headerRight={
      <>
        <button className="btn ghost sm"><Icons.Pause/>暂停</button>
        <button className="btn danger sm"><Icons.X/>取消</button>
      </>
    }
  >
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Stepper */}
      <div className="card" style={{ padding: "20px 24px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
          <div className="label">阶段流程</div>
          <div className="small" style={{ color: "var(--fg-mute)" }}>phase_route.py · single source of truth</div>
        </div>
        <PhaseStepper current={0} fraction={null}/>
      </div>

      {/* 2-col grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 20 }}>
        {/* Current ticket */}
        <div className="card" style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="label">当前票据</span>
            <span className="state-dot pulse" style={{ background: "var(--state-running)", color: "var(--state-running)" }}/>
            <span className="mono" style={{ fontSize: 12, color: "var(--fg-mute)" }}>#t-0042</span>
            <span style={{ fontSize: 15, fontWeight: 600, marginLeft: 4 }}>long-task-requirements</span>
            <span className="chip code" style={{ marginLeft: "auto", color: "#D2A8FF" }}>claude</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--fg-dim)", fontSize: 12 }}>
            <Icons.Clock size={12}/><span>2m 14s</span>
            <span style={{ color: "var(--fg-faint)" }}>·</span>
            <span>32 events</span>
            <span style={{ color: "var(--fg-faint)" }}>·</span>
            <span>turn 8</span>
            <span style={{ color: "var(--fg-faint)" }}>·</span>
            <Icons.DollarSign size={12}/><span>$0.14</span>
          </div>
          <div style={{ background: "var(--bg-inset)", border: "1px solid var(--border-subtle)", borderRadius: 6, padding: "10px 14px" }}>
            <div className="label" style={{ fontSize: 10, marginBottom: 4 }}>最近事件 · stream-json</div>
            <EventLine type="tool_use" text="Read(/docs/plans/2026-04-21-harness-srs.md)"/>
            <EventLine type="tool_result" text="{ bytes: 54021, lines: 849, ok: true }"/>
            <EventLine type="thinking" text="Scanning FR-001..050 to extract pain points..."/>
            <EventLine type="tool_use" text="AskUserQuestion(single_select, 3 options)"/>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn secondary sm"><Icons.ExternalLink/>查看票据流</button>
            <button className="btn ghost sm"><Icons.Copy/>复制 ticket id</button>
          </div>
        </div>

        {/* Metrics */}
        <div className="card" style={{ padding: "8px 20px" }}>
          <div className="label" style={{ padding: "10px 0", borderBottom: "1px solid var(--border-subtle)" }}>运行指标</div>
          <Metric icon={<Icons.DollarSign size={14}/>} label="成本" value="$0.14 / $5.00" mono color="var(--fg)"/>
          <Metric icon={<Icons.RefreshCw size={14}/>} label="Turns" value="8" mono/>
          <Metric icon={<Icons.Clock size={14}/>} label="时长" value="14m 22s" mono/>
          <Metric icon={<Icons.Cpu size={14}/>} label="工具" value="claude · sonnet-4.5" mono color="var(--accent-2)"/>
          <Metric icon={<Icons.Book size={14}/>} label="Skill" value="long-task-requirements"/>
          <Metric icon={<Icons.GitCommit size={14}/>} label="HEAD" value="de507b2" mono color="var(--accent-3)"/>
        </div>
      </div>

      {/* Recent stream */}
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ display: "flex", alignItems: "center", padding: "14px 20px", borderBottom: "1px solid var(--border-subtle)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="h3">近期票据流</span>
            <span className="chip outline">最近 10</span>
          </div>
          <button className="btn ghost sm" style={{ marginLeft: "auto" }}>查看全部<Icons.Chevron/></button>
        </div>
        <div>
          {tickets.map((t, i) => <TicketCard key={t.id} {...t} selected={i === 0}/>)}
        </div>
      </div>
    </div>
  </PageFrame>
);

window.RunOverviewPage = RunOverviewPage;
