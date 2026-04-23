/* global PageFrame, Icons */

const RadioRow = ({ label, desc, checked, onClick, kind = "radio" }) => (
  <div onClick={onClick} style={{
    display: "flex", alignItems: "flex-start", gap: 12, padding: "12px 14px",
    borderRadius: 6, cursor: "pointer",
    background: checked ? "var(--bg-active)" : "transparent",
    border: `1px solid ${checked ? "var(--accent)" : "var(--border-subtle)"}`,
    transition: "all 120ms",
  }}>
    <div style={{
      width: 16, height: 16, borderRadius: kind === "check" ? 4 : "50%",
      border: `1.5px solid ${checked ? "var(--accent)" : "var(--border-strong)"}`,
      background: checked ? "var(--accent)" : "transparent",
      display: "grid", placeItems: "center", flex: "none", marginTop: 2,
    }}>
      {checked && (kind === "check"
        ? <Icons.Check size={10} style={{ color: "#06101E", strokeWidth: 3 }}/>
        : <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#06101E" }}/>)}
    </div>
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ fontSize: 13.5, fontWeight: 500, color: "var(--fg)" }}>{label}</div>
      {desc && <div className="small" style={{ marginTop: 2, fontSize: 12 }}>{desc}</div>}
    </div>
  </div>
);

const HILCard = ({ phase, phaseColor, ticketId, title, body, variant = "single", options = [], answered }) => (
  <div className="card" style={{ padding: 0, overflow: "hidden", opacity: answered ? 0.5 : 1 }}>
    <div style={{
      display: "flex", alignItems: "center", gap: 10, padding: "14px 20px",
      background: `linear-gradient(90deg, ${phaseColor}14 0%, transparent 60%)`,
      borderBottom: "1px solid var(--border-subtle)",
    }}>
      <div style={{ width: 28, height: 28, borderRadius: 6, display: "grid", placeItems: "center", background: "rgba(245,181,68,0.12)", color: "var(--state-hil)" }}>
        <Icons.HelpCircle size={15}/>
      </div>
      <span className="mono" style={{ fontSize: 11.5, color: "var(--fg-mute)" }}>{ticketId}</span>
      <span style={{ fontSize: 14.5, fontWeight: 600, color: "var(--fg)" }}>{title}</span>
      <span className="chip outline" style={{ marginLeft: "auto", color: phaseColor, borderColor: `${phaseColor}44` }}>
        <span className="dot" style={{ background: phaseColor }}/>
        Phase · {phase}
      </span>
    </div>
    <div style={{ padding: 20 }}>
      <div className="body" style={{ color: "var(--fg)", lineHeight: 1.65, marginBottom: 16 }}>{body}</div>

      {variant === "single" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {options.map((o, i) => <RadioRow key={i} {...o}/>)}
        </div>
      )}
      {variant === "multi" && (
        <>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <span className="label" style={{ fontSize: 10.5 }}>选择要延期的 FR</span>
            <span className="chip outline" style={{ marginLeft: "auto" }}>已选 2 / 4</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {options.map((o, i) => <RadioRow key={i} {...o} kind="check"/>)}
          </div>
        </>
      )}
      {variant === "free" && (
        <div>
          <div className="label" style={{ fontSize: 10.5, marginBottom: 6 }}>你的回答</div>
          <div style={{
            minHeight: 140, border: "1px solid var(--border)", borderRadius: 6,
            background: "var(--bg-inset)", padding: 12,
            fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--fg-dim)"
          }}>
            <div style={{ color: "var(--fg-mute)" }}>// 例如：AuthService 应从 Session 中抽离，保持单一职责...</div>
            <div style={{ marginTop: 12, borderLeft: "2px solid var(--accent)", paddingLeft: 8, color: "var(--fg)" }}>
              类图边界建议以 Domain / Application / Infrastructure 三层划分；
              <span style={{ background: "rgba(110,168,254,0.12)" }}>Session 仓储</span> 放在 Infrastructure，
              由 Domain 层通过 repository port 注入。
            </div>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}>
            <span className="small" style={{ fontSize: 11 }}>Markdown 支持 · 引用 SRS 以 <code className="mono" style={{ color: "var(--accent-2)" }}>[FR-012]</code></span>
            <span className="mono small" style={{ fontSize: 11 }}>142 / 2000</span>
          </div>
        </div>
      )}
    </div>
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 20px", borderTop: "1px solid var(--border-subtle)", background: "var(--bg-surface-alt)" }}>
      <button className="btn ghost sm" disabled><Icons.Clock/>暂缓</button>
      <span className="small" style={{ fontSize: 11, color: "var(--fg-mute)" }}>此问题阻塞 phase_route — 必须回答</span>
      <button className="btn secondary sm" style={{ marginLeft: "auto" }}>草稿保存</button>
      <button className="btn primary sm"><Icons.Check/>提交答复</button>
    </div>
  </div>
);

const HILInboxPage = () => (
  <PageFrame
    active="hil"
    title="HIL 待答"
    hilCount={3}
    subtitle={
      <span className="chip solid" style={{ color: "var(--state-hil)", background: "rgba(245,181,68,0.1)", borderColor: "rgba(245,181,68,0.3)" }}>
        <span className="dot" style={{ background: "var(--state-hil)" }}/>3 条待答
      </span>
    }
    headerRight={<button className="btn ghost sm"><Icons.Filter/>筛选</button>}
  >
    <div style={{ padding: "24px 32px", maxWidth: 760, margin: "0 auto", display: "flex", flexDirection: "column", gap: 18 }}>

      <HILCard
        phase="Requirements" phaseColor="var(--phase-req)"
        ticketId="#t-0039" title="确认 HIL PoC 成功率门槛"
        body="14-skill 管线的 PoC 验证需要固定一个自动恢复率门槛，用于判定 Milestone 1 达成。不同门槛会影响重试策略与 classifier 召回率目标。"
        variant="single"
        options={[
          { label: "20 次循环 ≥ 90%", desc: "宽松门槛，快速 PoC；可接受偶发 context_overflow 中止", checked: false },
          { label: "25 次循环 ≥ 95%", desc: "推荐：与 SRS NFR-002 可靠性目标一致", checked: true },
          { label: "30 次循环 ≥ 98%", desc: "严格门槛，PoC 周期 +40% · 需要额外 classifier 训练数据", checked: false },
        ]}
      />

      <HILCard
        phase="UCD" phaseColor="var(--phase-ucd)"
        ticketId="#t-0046" title="选择本版本延期的 FR"
        body="根据 Lite 轨道的 8 周窗口容量估算，以下 4 条 FR 建议延后到 v1.1。请确认可以延期的项；至少保留 1 项。"
        variant="multi"
        options={[
          { label: "FR-035b 文档 ROI 下游 skill 消费链分析", desc: "需建立 skill → 文档节的静态解析索引", checked: true },
          { label: "FR-033b Skill 可视化编辑（表单模式）", desc: "当前仅提供文本编辑；结构化编辑依赖 skill schema", checked: true },
          { label: "FR-042 commits 聚合统计面板", desc: "按 feature / author / phase 的统计图", checked: false },
          { label: "FR-021 Per-Ticket 模型覆写高级 UI", desc: "保留后端能力，UI 推迟", checked: false },
        ]}
      />

      <HILCard
        phase="Design" phaseColor="var(--phase-design)"
        ticketId="#t-0053" title="描述期望的类图边界"
        body="classifier 与 ToolAdapter 之间的依赖方向存在争议：自由文本回答，建议引用 SRS FR 编号以便下游 skill 追溯。"
        variant="free"
      />

    </div>
  </PageFrame>
);

window.HILInboxPage = HILInboxPage;
