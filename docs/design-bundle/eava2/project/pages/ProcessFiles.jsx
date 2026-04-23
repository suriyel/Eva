/* global PageFrame, Icons */

const FormField = ({ label, value, mono, trace, error, suffix, width }) => (
  <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div className="label" style={{ fontSize: 10 }}>{label}</div>
      {trace && <span className="mono" style={{ fontSize: 9.5, color: "var(--fg-mute)" }}>{trace}</span>}
      {error && <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--state-fail)", display: "flex", alignItems: "center", gap: 4 }}><Icons.AlertCircle size={10}/>缺失</span>}
    </div>
    <div className="input" style={{
      fontFamily: mono ? "var(--font-mono)" : "inherit", fontSize: mono ? 12.5 : 13,
      display: "flex", alignItems: "center", gap: 8, maxWidth: width,
      borderColor: error ? "var(--state-fail)" : "var(--border)",
      boxShadow: error ? "0 0 0 2px rgba(242,109,109,0.15)" : "none",
    }}>
      <span style={{ flex: 1 }}>{value}</span>
      {suffix}
    </div>
  </div>
);

const Issue = ({ severity, ref_, msg }) => {
  const map = {
    ok: { c: "var(--state-done)", bg: "rgba(62,207,142,0.08)", icon: <Icons.Check size={12}/> },
    warn: { c: "var(--state-hil)", bg: "rgba(245,181,68,0.08)", icon: <Icons.AlertTriangle size={12}/> },
    err: { c: "var(--state-fail)", bg: "rgba(242,109,109,0.08)", icon: <Icons.AlertCircle size={12}/> },
  };
  const s = map[severity];
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "10px 12px", borderRadius: 6, background: s.bg, border: `1px solid ${s.c}22`, cursor: "pointer" }}>
      <span style={{ color: s.c, marginTop: 2 }}>{s.icon}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className="mono" style={{ fontSize: 10.5, color: s.c, fontWeight: 600 }}>{ref_}</span>
        </div>
        <div style={{ fontSize: 12, color: "var(--fg)", marginTop: 3, lineHeight: 1.5 }}>{msg}</div>
      </div>
    </div>
  );
};

const ProcessFilesPage = () => (
  <PageFrame
    active="process"
    title="过程文件"
    subtitle={<span className="chip outline"><span className="dot" style={{ background: "var(--state-hil)" }}/>未保存</span>}
    headerRight={
      <>
        <button className="btn ghost sm">还原更改</button>
        <button className="btn primary sm"><Icons.Save/>保存并提交</button>
      </>
    }
  >
    <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 16, height: "100%", minHeight: 0 }}>
      {/* File chips */}
      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
        {[
          { label: "feature-list.json", active: true, icon: <Icons.File size={12}/>, dirty: true },
          { label: "env-guide.md", icon: <Icons.File size={12}/> },
          { label: "long-task-guide.md", icon: <Icons.File size={12}/> },
          { label: ".env.example", icon: <Icons.File size={12}/> },
        ].map((c, i) => (
          <div key={i} style={{
            display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", borderRadius: 6,
            background: c.active ? "rgba(110,168,254,0.1)" : "var(--bg-surface)",
            border: `1px solid ${c.active ? "rgba(110,168,254,0.3)" : "var(--border)"}`,
            color: c.active ? "var(--accent)" : "var(--fg-dim)", cursor: "pointer", fontSize: 12, fontFamily: "var(--font-mono)",
          }}>
            {c.icon}{c.label}
            {c.dirty && <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--state-hil)" }}/>}
          </div>
        ))}
      </div>

      <div style={{ flex: 1, display: "flex", gap: 16, minHeight: 0 }}>
        {/* Structured form */}
        <div className="card" style={{ flex: 1, overflow: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
          <div>
            <div className="h3" style={{ marginBottom: 4 }}>Project</div>
            <div className="small">项目元数据 · 来源 feature-list.json 根字段</div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <FormField label="name" value="harness" mono/>
            <FormField label="version" value="1.0.0-rc.1" mono/>
          </div>

          <div style={{ marginTop: 8 }}>
            <div className="h3" style={{ marginBottom: 4 }}>Tech Stack</div>
            <div className="small">下游 work/feature-design skill 将读取</div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14 }}>
            <FormField label="language" value="python 3.12" mono/>
            <FormField label="test_framework" value="pytest + pytest-asyncio" mono/>
            <FormField label="coverage_tool" value="coverage.py" mono/>
          </div>

          <div style={{ marginTop: 8 }}>
            <div className="h3" style={{ marginBottom: 4 }}>Features</div>
            <div className="small">本轮 run 将派生的 feature 集合 · 共 4 条</div>
          </div>
          <div style={{ border: "1px solid var(--border-subtle)", borderRadius: 6, overflow: "hidden" }}>
            <div style={{ display: "grid", gridTemplateColumns: "80px 1fr 110px 1fr 24px", background: "var(--bg-surface-alt)", padding: "10px 14px", borderBottom: "1px solid var(--border-subtle)" }}>
              {["id", "title", "status", "srs_trace", ""].map(h => <div key={h} className="label" style={{ fontSize: 10 }}>{h}</div>)}
            </div>
            {[
              { id: "feature-01", title: "Ticket 持久化 + JSONL audit", status: "pending", trace: "FR-005, FR-006", err: false },
              { id: "feature-02", title: "HIL 捕获与 pty 回写", status: "pending", trace: "FR-009, FR-010", err: false },
              { id: "feature-03", title: "异常分类 + 指数退避", status: "pending", trace: "—", err: true },
              { id: "feature-04", title: "Per-Skill 模型覆写", status: "pending", trace: "FR-021", err: false },
            ].map((f, i) => (
              <div key={f.id} style={{ display: "grid", gridTemplateColumns: "80px 1fr 110px 1fr 24px", padding: "10px 14px", alignItems: "center", borderBottom: i < 3 ? "1px solid var(--border-subtle)" : "none", background: f.err ? "rgba(242,109,109,0.05)" : i % 2 ? "var(--bg-surface-alt)" : "transparent", fontSize: 12.5 }}>
                <span className="mono" style={{ fontSize: 11.5, color: "var(--accent-3)" }}>{f.id}</span>
                <span>{f.title}</span>
                <span className="chip outline" style={{ width: "fit-content", height: 18 }}><span className="dot" style={{ background: "var(--state-pending)" }}/>{f.status}</span>
                <span className="mono" style={{ fontSize: 11, color: f.err ? "var(--state-fail)" : "var(--fg-dim)" }}>{f.trace}</span>
                <Icons.MoreH size={14} style={{ color: "var(--fg-mute)" }}/>
              </div>
            ))}
          </div>
          <button className="btn secondary sm" style={{ width: "fit-content" }}><Icons.Plus/>添加特性</button>
        </div>

        {/* Validation panel */}
        <div style={{ width: 340, flex: "none", display: "flex", flexDirection: "column" }}>
          <div className="card" style={{ padding: 0, overflow: "hidden", display: "flex", flexDirection: "column", minHeight: 0 }}>
            <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--border-subtle)", display: "flex", alignItems: "center", gap: 10 }}>
              <span className="h3" style={{ fontSize: 14 }}>校验面板</span>
              <span className="chip outline">3 issues</span>
              <button className="btn ghost sm" style={{ marginLeft: "auto" }}><Icons.RefreshCw/></button>
            </div>
            <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 8, overflow: "auto" }}>
              <div className="label" style={{ fontSize: 10, padding: "4px 4px" }}>实时校验 · Zod schema</div>
              <Issue severity="ok" ref_="schema" msg="JSON schema 结构校验通过 · 4 features · 0 孤立字段"/>
              <Issue severity="err" ref_="FR-014 · feature-03" msg="srs_trace 缺失 · 该特性必须追溯到至少一条 FR，否则下游 feature-design skill 无法开始。"/>

              <div className="label" style={{ fontSize: 10, padding: "8px 4px 4px" }}>后端校验 · validate_features.py</div>
              <Issue severity="warn" ref_="NFR-003 · feature-01" msg="依赖 feature-02（HIL 捕获）但未声明于 dependencies 数组。建议声明以保证 ST 顺序。"/>
              <Issue severity="ok" ref_="quality_gates" msg="coverage_threshold 0.85 满足 ats 阶段门槛"/>
              <Issue severity="ok" ref_="naming" msg="feature-id 命名格式 feature-NN 合规"/>
            </div>
            <div style={{ padding: 10, borderTop: "1px solid var(--border-subtle)", background: "var(--bg-surface-alt)" }}>
              <button className="btn secondary sm" style={{ width: "100%", justifyContent: "center" }}>
                <Icons.Terminal/>再次运行 validate_features.py
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </PageFrame>
);

window.ProcessFilesPage = ProcessFilesPage;
