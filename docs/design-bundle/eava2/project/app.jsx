/* global RunOverviewPage, HILInboxPage, SystemSettingsPage, PromptsAndSkillsPage, TicketStreamPage, DocsAndROIPage, ProcessFilesPage, CommitHistoryPage */

const Cover = () => (
  <div className="hns" style={{
    width: "100%", height: "100%", display: "flex", flexDirection: "column",
    background: "radial-gradient(ellipse at top, #141A24 0%, var(--bg-app) 55%)",
    padding: "80px 80px 60px", borderRadius: 10, overflow: "hidden", position: "relative",
  }}>
    <div className="grid-bg" style={{ position: "absolute", inset: 0, opacity: 0.6 }}/>
    <div style={{ position: "relative" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 48 }}>
        <div style={{
          width: 44, height: 44, borderRadius: 10,
          background: "linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%)",
          display: "grid", placeItems: "center", boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.18), 0 6px 24px rgba(110,168,254,0.3)"
        }}>
          <div style={{ width: 18, height: 18, border: "2px solid #0A0D12", borderRadius: 3, transform: "rotate(45deg)" }}/>
        </div>
        <div>
          <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.015em" }}>Harness</div>
          <div className="mono small" style={{ fontSize: 11 }}>Cockpit Dark · UCD v1 · 2026-04-21</div>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
          <span className="chip outline">UCD · ISO/IEC/IEEE 29148 对齐</span>
          <span className="mono small" style={{ fontSize: 10.5, color: "var(--fg-mute)" }}>SRS ↔ 8 pages ↔ 15 components</span>
        </div>
      </div>

      <div style={{ fontSize: 56, fontWeight: 600, letterSpacing: "-0.025em", lineHeight: 1.05, maxWidth: 900 }}>
        驱动 long-task 管线的<br/>
        <span style={{ color: "var(--accent)" }}>桌面外部包裹层</span> —
        <span style={{ color: "var(--fg-dim)" }}> UI 概念设计</span>
      </div>
      <div style={{ fontSize: 16, color: "var(--fg-dim)", maxWidth: 720, marginTop: 24, lineHeight: 1.6 }}>
        为 Harness 14-skill 自动编排场景设计的深色驾驶舱界面。围绕 Run · Ticket · HIL · Phase 四个第一公民概念构建；
        8 个页面覆盖 SRS FR-001..050 全部交互路径。
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginTop: 64, maxWidth: 1100 }}>
        {[
          { k: "8", l: "核心页面", c: "var(--accent)" },
          { k: "15", l: "组件", c: "var(--accent-2)" },
          { k: "50", l: "FR 覆盖", c: "var(--accent-3)" },
          { k: "1", l: "Dark theme · v1", c: "var(--state-running)" },
        ].map(s => (
          <div key={s.l} style={{ padding: "18px 20px", border: "1px solid var(--border-subtle)", borderRadius: 10, background: "rgba(18,22,29,0.7)", backdropFilter: "blur(4px)" }}>
            <div className="mono" style={{ fontSize: 32, fontWeight: 600, color: s.c, lineHeight: 1 }}>{s.k}</div>
            <div className="small" style={{ marginTop: 6, fontSize: 12 }}>{s.l}</div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: "auto", paddingTop: 40, display: "flex", alignItems: "center", gap: 16 }}>
        <div style={{ display: "flex", gap: 6 }}>
          {["var(--phase-req)", "var(--phase-ucd)", "var(--phase-design)", "var(--phase-ats)", "var(--phase-init)", "var(--phase-work)", "var(--phase-st)", "var(--phase-finalize)"].map((c, i) => (
            <div key={i} style={{ width: 28, height: 4, borderRadius: 2, background: c }}/>
          ))}
        </div>
        <div className="mono small" style={{ fontSize: 11, color: "var(--fg-mute)" }}>8 phases · requirements → ucd → design → ats → init → work → st → finalize</div>
      </div>
    </div>
  </div>
);

const App = () => (
  <DesignCanvas
    title="Harness — UCD · Cockpit Dark"
    subtitle="8 pages + 1 cover · 深色驾驶舱 UI"
    background="#060810"
  >
    <DCSection id="overview" title="00 · 封面">
      <DCArtboard id="cover" label="Cover · Harness UCD" width={1280} height={800}>
        <Cover/>
      </DCArtboard>
    </DCSection>

    <DCSection id="primary" title="01 · 主工作流 · Run 与 HIL">
      <DCArtboard id="p-overview" label="4.1 · RunOverview · 总览" width={1280} height={900}>
        <RunOverviewPage/>
      </DCArtboard>
      <DCArtboard id="p-hil" label="4.2 · HILInbox · HIL 待答" width={1280} height={1100}>
        <HILInboxPage/>
      </DCArtboard>
      <DCArtboard id="p-stream" label="4.5 · TicketStream · 票据流" width={1440} height={840}>
        <TicketStreamPage/>
      </DCArtboard>
    </DCSection>

    <DCSection id="artifacts" title="02 · 过程产物 · 文档 · 提交 · 校验">
      <DCArtboard id="p-docs" label="4.6 · DocsAndROI · 文档" width={1440} height={900}>
        <DocsAndROIPage/>
      </DCArtboard>
      <DCArtboard id="p-process" label="4.7 · ProcessFiles · 过程文件编辑" width={1440} height={920}>
        <ProcessFilesPage/>
      </DCArtboard>
      <DCArtboard id="p-commits" label="4.8 · CommitHistory · 提交历史" width={1440} height={860}>
        <CommitHistoryPage/>
      </DCArtboard>
    </DCSection>

    <DCSection id="config" title="03 · 配置 · Skills 与系统设置">
      <DCArtboard id="p-skills" label="4.4 · PromptsAndSkills · Skills" width={1280} height={820}>
        <PromptsAndSkillsPage/>
      </DCArtboard>
      <DCArtboard id="p-settings" label="4.3 · SystemSettings · 设置" width={1280} height={980}>
        <SystemSettingsPage/>
      </DCArtboard>
    </DCSection>
  </DesignCanvas>
);

ReactDOM.createRoot(document.getElementById("root")).render(<App/>);
