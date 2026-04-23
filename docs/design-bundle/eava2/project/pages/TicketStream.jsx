/* global PageFrame, TicketCard, Icons */

const streamEvents = [
  { type: "text", depth: 0, expanded: true, summary: "#t-0042 · long-task-requirements", time: "14:22:18" },
  { type: "tool_use", depth: 1, summary: "Read(/docs/plans/2026-04-21-harness-srs.md)", time: "14:22:19", ok: true },
  { type: "tool_result", depth: 1, summary: '{ "bytes": 54021, "lines": 849, "ok": true }', time: "14:22:19" },
  { type: "thinking", depth: 1, summary: "Scanning FR-001..050 for coverage gaps in pain map…", time: "14:22:21" },
  { type: "tool_use", depth: 1, summary: "Grep(pattern='FR-\\d+', path='docs/plans/')", time: "14:22:22", selected: true },
  { type: "tool_result", depth: 1, summary: "matched 48 FR ids · unique 46", time: "14:22:22" },
  { type: "text", depth: 1, summary: "发现 FR-035b 未关联到任何痛点行，将通过 HIL 请求确认。", time: "14:22:23" },
  { type: "tool_use", depth: 1, summary: "AskUserQuestion(multi_select, options=4)", time: "14:22:24", hil: true },
  { type: "tool_use", depth: 1, summary: "Write(.harness/session/state.json)", time: "14:22:25", denied: true },
  { type: "tool_result", depth: 1, summary: "permission_denial: path outside .harness-workdir/", time: "14:22:25", denied: true },
];

const EventRow = ({ ev }) => {
  const typeMap = {
    tool_use: { c: "var(--accent-2)", bg: "rgba(177,146,251,0.14)" },
    tool_result: { c: "var(--accent-3)", bg: "rgba(125,219,211,0.14)" },
    text: { c: "var(--fg-dim)", bg: "var(--bg-surface-alt)" },
    thinking: { c: "var(--state-hil)", bg: "rgba(245,181,68,0.14)" },
    error: { c: "var(--state-fail)", bg: "rgba(242,109,109,0.14)" },
  };
  const t = typeMap[ev.type];
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10, padding: "6px 14px",
      paddingLeft: 14 + ev.depth * 20,
      borderLeft: ev.denied ? "2px solid var(--state-fail)" : "2px solid transparent",
      background: ev.selected ? "var(--bg-active)" : "transparent",
      fontFamily: "var(--font-mono)", fontSize: 12,
      cursor: "pointer",
    }}>
      <Icons.Chevron size={11} style={{ color: "var(--fg-mute)", flex: "none" }}/>
      <span style={{
        display: "inline-flex", padding: "1.5px 7px", borderRadius: 3,
        fontSize: 10, fontWeight: 600, letterSpacing: "0.02em",
        color: t.c, background: t.bg, flex: "none", fontFamily: "var(--font-mono)"
      }}>{ev.type}</span>
      {ev.hil && <span className="chip solid" style={{ height: 17, fontSize: 9.5, color: "var(--state-hil)", borderColor: "rgba(245,181,68,0.3)", background: "rgba(245,181,68,0.08)" }}><Icons.HelpCircle size={10}/>HIL</span>}
      {ev.denied && <span className="chip solid" style={{ height: 17, fontSize: 9.5, color: "var(--state-fail)", borderColor: "rgba(242,109,109,0.3)", background: "rgba(242,109,109,0.08)" }}>denied</span>}
      <span style={{ flex: 1, color: ev.selected ? "var(--fg)" : "var(--fg-dim)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{ev.summary}</span>
      <span style={{ fontSize: 10.5, color: "var(--fg-faint)" }}>{ev.time}</span>
    </div>
  );
};

const TicketStreamPage = () => (
  <PageFrame
    active="stream"
    title="Ticket 流"
    subtitle={<span className="chip code">#run-26.04.21-001</span>}
    headerRight={
      <>
        <button className="btn ghost sm"><Icons.Download/>导出</button>
      </>
    }
  >
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Filter bar */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 20px", borderBottom: "1px solid var(--border-subtle)", background: "var(--bg-surface)" }}>
        <div className="input" style={{ width: 280, display: "flex", alignItems: "center", gap: 8, height: 30 }}>
          <Icons.Search size={13} style={{ color: "var(--fg-mute)" }}/>
          <span style={{ color: "var(--fg-mute)", fontSize: 12.5, flex: 1 }}>搜索 ticket / skill / 事件…</span>
          <kbd>⌘F</kbd>
        </div>
        <button className="btn secondary sm"><Icons.Filter/>状态<span className="chip outline" style={{ height: 16, fontSize: 9.5 }}>2</span></button>
        <button className="btn secondary sm">工具</button>
        <button className="btn secondary sm">Skill</button>
        <button className="btn ghost sm" style={{ marginLeft: "auto" }}>清除</button>
        <span className="chip outline">共 48 · 筛后 12</span>
      </div>

      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        {/* Ticket list */}
        <div style={{ width: 320, borderRight: "1px solid var(--border-subtle)", overflow: "auto", flex: "none" }}>
          {[
            { id: "#t-0042", skill: "long-task-requirements", tool: "claude", state: "running", status: "2m 14s", events: 32 },
            { id: "#t-0041", skill: "phase-router", tool: "claude", state: "completed", status: "11s", events: 4 },
            { id: "#t-0039", skill: "requirements-draft", tool: "opencode", state: "hil_waiting", status: "1m 02s", events: 18 },
            { id: "#t-0038", skill: "context-scanner", tool: "claude", state: "completed", status: "34s", events: 27 },
            { id: "#t-0037", skill: "pain-extractor", tool: "claude", state: "retrying", status: "3/5", events: 9 },
            { id: "#t-0036", skill: "using-opencode", tool: "opencode", state: "failed", status: "context", events: 14 },
            { id: "#t-0035", skill: "run-init", tool: "claude", state: "completed", status: "2s", events: 2 },
          ].map((t, i) => <TicketCard key={t.id} {...t} selected={i === 0}/>)}
        </div>

        {/* Stream tree */}
        <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", background: "var(--bg-app)" }}>
          <div style={{ padding: "12px 16px", display: "flex", alignItems: "center", gap: 10, borderBottom: "1px solid var(--border-subtle)" }}>
            <span className="label">stream-json · #t-0042</span>
            <span className="chip outline">32 events · 58 KB</span>
            <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6, color: "var(--fg-mute)", fontSize: 11.5 }}>
              <span className="state-dot pulse" style={{ background: "var(--state-running)", color: "var(--state-running)", width: 6, height: 6 }}/>
              live · auto-scroll
            </span>
          </div>
          <div style={{ flex: 1, overflow: "auto", padding: "8px 0" }}>
            {streamEvents.map((ev, i) => <EventRow key={i} ev={ev}/>)}
            {/* Expanded JSON body for selected */}
            <div style={{ margin: "4px 14px 14px 54px", padding: 14, background: "var(--bg-inset)", borderRadius: 6, border: "1px solid var(--border-subtle)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                <span className="label" style={{ fontSize: 10 }}>tool_use · Grep</span>
                <span className="mono" style={{ fontSize: 10.5, color: "var(--fg-mute)", marginLeft: "auto" }}>242 B · 14ms</span>
              </div>
              <div className="mono" style={{ fontSize: 12.5, lineHeight: 1.7 }}>
                <div><span style={{ color: "var(--code-com)" }}>{"{"}</span></div>
                <div style={{ paddingLeft: 16 }}><span style={{ color: "var(--code-fn)" }}>"pattern"</span>: <span style={{ color: "var(--code-str)" }}>"FR-\\d+"</span>,</div>
                <div style={{ paddingLeft: 16 }}><span style={{ color: "var(--code-fn)" }}>"path"</span>: <span style={{ color: "var(--code-str)" }}>"docs/plans/"</span>,</div>
                <div style={{ paddingLeft: 16 }}><span style={{ color: "var(--code-fn)" }}>"output_mode"</span>: <span style={{ color: "var(--code-str)" }}>"count"</span></div>
                <div><span style={{ color: "var(--code-com)" }}>{"}"}</span></div>
              </div>
            </div>
            {streamEvents.slice(7).map((ev, i) => <EventRow key={"b"+i} ev={ev}/>)}
          </div>
        </div>

        {/* Inspector */}
        <div style={{ width: 340, flex: "none", borderLeft: "1px solid var(--border-subtle)", background: "var(--bg-surface)", display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", gap: 2, padding: "10px 12px", borderBottom: "1px solid var(--border-subtle)" }}>
            {["事件", "元数据", "Raw"].map((t, i) => (
              <div key={t} style={{
                padding: "6px 12px", borderRadius: 4, fontSize: 12, fontWeight: 500,
                color: i === 0 ? "var(--fg)" : "var(--fg-mute)",
                background: i === 0 ? "var(--bg-active)" : "transparent", cursor: "pointer"
              }}>{t}</div>
            ))}
          </div>
          <div style={{ padding: 16, overflow: "auto", flex: 1 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div>
                <div className="label" style={{ fontSize: 10, marginBottom: 4 }}>事件 ID</div>
                <div className="mono" style={{ fontSize: 12 }}>evt_26042_grep_014</div>
              </div>
              <div>
                <div className="label" style={{ fontSize: 10, marginBottom: 4 }}>类型</div>
                <span className="chip solid" style={{ color: "var(--accent-2)", background: "rgba(177,146,251,0.12)", borderColor: "rgba(177,146,251,0.25)" }}>tool_use · Grep</span>
              </div>
              <div>
                <div className="label" style={{ fontSize: 10, marginBottom: 4 }}>时间戳</div>
                <div className="mono" style={{ fontSize: 12 }}>2026-04-21 14:22:22.418</div>
              </div>
              <div>
                <div className="label" style={{ fontSize: 10, marginBottom: 4 }}>耗时 / 大小</div>
                <div className="mono" style={{ fontSize: 12 }}>14ms · 242 B</div>
              </div>
              <div className="divider" style={{ margin: "8px 0" }}/>
              <div>
                <div className="label" style={{ fontSize: 10, marginBottom: 6 }}>Actions</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <button className="btn secondary sm" style={{ justifyContent: "flex-start" }}><Icons.Download/>导出 JSON</button>
                  <button className="btn secondary sm" style={{ justifyContent: "flex-start" }}><Icons.RefreshCw/>重新分类</button>
                  <button className="btn ghost sm" style={{ justifyContent: "flex-start" }}><Icons.Copy/>复制到剪贴板</button>
                </div>
              </div>
              <div className="divider" style={{ margin: "8px 0" }}/>
              <div>
                <div className="label" style={{ fontSize: 10, marginBottom: 6 }}>Classifier 判定</div>
                <div style={{ border: "1px solid var(--border-subtle)", borderRadius: 6, padding: 10, background: "var(--bg-inset)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span className="chip solid" style={{ color: "var(--state-done)", background: "rgba(62,207,142,0.1)", borderColor: "rgba(62,207,142,0.25)" }}>CONTINUE</span>
                    <span className="mono" style={{ fontSize: 11, color: "var(--fg-mute)", marginLeft: "auto" }}>p=0.92</span>
                  </div>
                  <div className="small" style={{ marginTop: 6, fontSize: 11.5 }}>工具返回可用结果，无异常信号；skill 可继续下一步推理。</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </PageFrame>
);

window.TicketStreamPage = TicketStreamPage;
