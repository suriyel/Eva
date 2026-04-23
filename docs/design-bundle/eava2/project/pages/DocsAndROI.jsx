/* global PageFrame, Icons */

const DocsFileRow = ({ icon, label, size, depth = 0, active }) => (
  <div style={{
    display: "flex", alignItems: "center", gap: 8, padding: "6px 10px",
    paddingLeft: 10 + depth * 14,
    background: active ? "var(--bg-active)" : "transparent",
    borderLeft: active ? "2px solid var(--accent)" : "2px solid transparent",
    fontSize: 12.5, color: active ? "var(--fg)" : "var(--fg-dim)", cursor: "pointer",
  }}>
    <span style={{ color: active ? "var(--accent)" : "var(--fg-mute)", display: "flex" }}>{icon}</span>
    <span style={{ flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{label}</span>
    {size && <span className="mono" style={{ fontSize: 10, color: "var(--fg-mute)" }}>{size}</span>}
  </div>
);

const TocItem = ({ label, active, depth = 0 }) => (
  <div style={{
    padding: "4px 0", paddingLeft: 12 + depth * 12,
    fontSize: 11.5, color: active ? "var(--accent)" : "var(--fg-mute)", cursor: "pointer",
    borderLeft: active ? "2px solid var(--accent)" : "2px solid var(--border-subtle)",
    marginLeft: -1,
  }}>{label}</div>
);

const DocsAndROIPage = () => (
  <PageFrame
    active="docs"
    title="文档 & ROI"
    headerRight={
      <>
        <button className="btn ghost sm" disabled><Icons.Zap/>运行 ROI 分析 · v1.1</button>
        <button className="btn secondary sm"><Icons.Copy/>复制 Markdown</button>
      </>
    }
  >
    <div style={{ display: "flex", height: "100%", minHeight: 0 }}>
      {/* File tree */}
      <div style={{ width: 260, flex: "none", borderRight: "1px solid var(--border-subtle)", background: "var(--bg-surface)", overflow: "auto" }}>
        <div style={{ padding: 10 }}>
          <div className="label" style={{ padding: "6px 10px" }}>当前 Run</div>
          <DocsFileRow icon={<Icons.FolderOpen size={13}/>} label="docs/" depth={0}/>
          <DocsFileRow icon={<Icons.FolderOpen size={13}/>} label="plans/" depth={1}/>
          <DocsFileRow icon={<Icons.File size={13}/>} label="2026-04-21-harness-srs.md" size="54K" depth={2} active/>
          <DocsFileRow icon={<Icons.File size={13}/>} label="2026-04-21-harness-ucd.md" size="—" depth={2}/>
          <DocsFileRow icon={<Icons.File size={13}/>} label="2026-04-21-harness-deferred.md" size="3K" depth={2}/>
          <DocsFileRow icon={<Icons.Folder size={13}/>} label="features/" depth={1}/>
          <DocsFileRow icon={<Icons.Folder size={13}/>} label="test-cases/" depth={1}/>
          <div style={{ height: 10 }}/>
          <div className="label" style={{ padding: "6px 10px" }}>历史</div>
          <DocsFileRow icon={<Icons.Folder size={13}/>} label="2026-04-18-poc-scraper/" depth={0}/>
        </div>
      </div>

      {/* Reader */}
      <div style={{ flex: 1, overflow: "auto", minWidth: 0, position: "relative" }}>
        <div style={{ maxWidth: 780, margin: "0 auto", padding: "40px 48px 80px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <span className="chip outline">Approved</span>
            <span className="chip outline">Track · Lite</span>
            <span className="mono small" style={{ fontSize: 11, color: "var(--fg-mute)" }}>2026-04-21 · 849 lines · 54 KB</span>
          </div>
          <h1 style={{ fontSize: 30, fontWeight: 600, letterSpacing: "-0.02em", lineHeight: 1.2, marginBottom: 10 }}>
            Harness — 软件需求规约
          </h1>
          <div className="body" style={{ color: "var(--fg-dim)", marginBottom: 28, fontSize: 15, lineHeight: 1.6 }}>
            桌面外部包裹层，用于在单机单用户场景下自动编排 longtaskforagent 的 14-skill long-task 管线。
          </div>

          <h2 style={{ fontSize: 20, fontWeight: 600, marginTop: 40, marginBottom: 12, color: "var(--accent)" }}>1. 目的与范围</h2>
          <p className="body" style={{ marginBottom: 16, color: "var(--fg)" }}>
            Harness 驱动 Claude Code 与 OpenCode 交互会话，实现从 Requirements 到 ST Go verdict 的闭环自动执行。核心价值在于消除开发者手动起会话、手动路由、手动捕捉 HIL、手动切模型的负担。
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, margin: "20px 0" }}>
            <div style={{ padding: 14, border: "1px solid var(--border-subtle)", borderRadius: 6, background: "var(--bg-inset)" }}>
              <div className="label" style={{ fontSize: 10, marginBottom: 6, color: "var(--state-done)" }}>In Scope</div>
              <div className="small" style={{ fontSize: 12, color: "var(--fg)", lineHeight: 1.6 }}>14-skill 自动循环 · Claude + OpenCode 适配 · SQLite 票据 · HIL UI · 异常分类 + 退避 · 模型覆写 · 8 UI 视图</div>
            </div>
            <div style={{ padding: 14, border: "1px solid var(--border-subtle)", borderRadius: 6, background: "var(--bg-inset)" }}>
              <div className="label" style={{ fontSize: 10, marginBottom: 6, color: "var(--state-fail)" }}>Out of Scope</div>
              <div className="small" style={{ fontSize: 12, color: "var(--fg)", lineHeight: 1.6 }}>云端 / 多用户 · CI/CD 外部触发 · 移动端 · i18n · 插件市场 · 历史全文搜索</div>
            </div>
          </div>

          <h2 style={{ fontSize: 20, fontWeight: 600, marginTop: 40, marginBottom: 12, color: "var(--accent)" }}>1.3 问题陈述</h2>
          <div style={{
            background: "var(--bg-inset)", border: "1px solid var(--border-subtle)",
            borderLeft: "3px solid var(--accent-2)",
            borderRadius: 6, padding: "14px 18px", fontFamily: "var(--font-mono)", fontSize: 12.5, lineHeight: 1.75,
            marginBottom: 20,
          }}>
            <div style={{ color: "var(--code-com)" }}># 5-Whys</div>
            <div><span style={{ color: "var(--code-kw)" }}>Symptom:</span> <span style={{ color: "var(--fg)" }}>开发者需要多次手动起会话 + 手动路由 + 手动记录</span></div>
            <div><span style={{ color: "var(--code-kw)" }}>Why 1:</span> <span style={{ color: "var(--fg-dim)" }}>没有统一 orchestrator 驱动 14-skill 管线</span></div>
            <div><span style={{ color: "var(--code-kw)" }}>Why 2:</span> <span style={{ color: "var(--fg-dim)" }}>-p 非交互模式下 AskUserQuestion 失效</span></div>
            <div><span style={{ color: "var(--code-kw)" }}>Root:</span> <span style={{ color: "var(--accent-3)" }}>需要保留交互模式 + 自动编排 + 持久化 + 可视化的集成方案</span></div>
          </div>

          <div style={{ overflow: "hidden", border: "1px solid var(--border-subtle)", borderRadius: 6, marginTop: 12 }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
              <thead>
                <tr style={{ background: "var(--bg-surface-alt)" }}>
                  <th style={{ padding: "10px 14px", textAlign: "left", borderBottom: "1px solid var(--border-subtle)", color: "var(--fg-dim)", fontWeight: 500, fontSize: 10.5, textTransform: "uppercase", letterSpacing: "0.04em" }}>Pain</th>
                  <th style={{ padding: "10px 14px", textAlign: "left", borderBottom: "1px solid var(--border-subtle)", color: "var(--fg-dim)", fontWeight: 500, fontSize: 10.5, textTransform: "uppercase", letterSpacing: "0.04em" }}>Freq</th>
                  <th style={{ padding: "10px 14px", textAlign: "right", borderBottom: "1px solid var(--border-subtle)", color: "var(--fg-dim)", fontWeight: 500, fontSize: 10.5, textTransform: "uppercase", letterSpacing: "0.04em" }}>Score</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ["手动起 claude 会话并记 phase", "每 skill ≥1 次", 9, "var(--state-fail)"],
                  ["AskUserQuestion 在 -p 模式失效", "每 HIL 点", 9, "var(--state-fail)"],
                  ["rate_limit 需手动切会话", "每 run 数次", 6, "var(--state-hil)"],
                ].map((r, i) => (
                  <tr key={i} style={{ background: i % 2 ? "var(--bg-surface-alt)" : "transparent" }}>
                    <td style={{ padding: "10px 14px" }}>{r[0]}</td>
                    <td style={{ padding: "10px 14px", color: "var(--fg-dim)" }}>{r[1]}</td>
                    <td style={{ padding: "10px 14px", textAlign: "right", color: r[3], fontWeight: 600, fontFamily: "var(--font-mono)" }}>{r[2]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

        </div>
      </div>

      {/* TOC */}
      <div style={{ width: 200, flex: "none", padding: "40px 16px", overflow: "auto" }}>
        <div className="label" style={{ marginBottom: 10, paddingLeft: 12 }}>章节</div>
        <TocItem label="1. 目的与范围" active/>
        <TocItem label="1.1 In Scope" depth={1}/>
        <TocItem label="1.2 Out of Scope" depth={1}/>
        <TocItem label="1.3 问题陈述" depth={1}/>
        <TocItem label="2. 术语与定义"/>
        <TocItem label="3. 干系人"/>
        <TocItem label="4. 功能需求 (FR)"/>
        <TocItem label="5. 非功能需求"/>
        <TocItem label="6. 接口与数据模型"/>
        <TocItem label="7. 验收与追溯矩阵"/>
      </div>
    </div>
  </PageFrame>
);

window.DocsAndROIPage = DocsAndROIPage;
