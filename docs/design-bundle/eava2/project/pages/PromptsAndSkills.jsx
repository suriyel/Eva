/* global PageFrame, Icons */

const TreeNode = ({ icon, label, chip, active, depth = 0, expanded }) => (
  <div style={{
    display: "flex", alignItems: "center", gap: 6, padding: "6px 10px",
    paddingLeft: 10 + depth * 16, borderRadius: 4, cursor: "pointer",
    background: active ? "var(--bg-active)" : "transparent",
    color: active ? "var(--fg)" : "var(--fg-dim)",
    fontSize: 12.5,
    borderLeft: active ? "2px solid var(--accent)" : "2px solid transparent",
  }}>
    {expanded !== undefined && (
      expanded ? <Icons.ChevronDown size={11} style={{ color: "var(--fg-mute)" }}/> : <Icons.Chevron size={11} style={{ color: "var(--fg-mute)" }}/>
    )}
    <span style={{ color: active ? "var(--accent)" : "var(--fg-mute)", display: "flex" }}>{icon}</span>
    <span style={{ flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{label}</span>
    {chip && <span className="chip outline" style={{ height: 16, fontSize: 9.5, padding: "0 5px" }}>{chip}</span>}
  </div>
);

const PromptsAndSkillsPage = () => (
  <PageFrame
    active="skills"
    title="Skills"
    subtitle={<span className="chip code">plugins/longtaskforagent</span>}
    headerRight={
      <>
        <button className="btn ghost sm"><Icons.RefreshCw/>检查更新</button>
        <button className="btn secondary sm"><Icons.GitPullRequest/>更新 Plugin</button>
      </>
    }
  >
    <div style={{ display: "flex", height: "calc(100% - 0px)", minHeight: 0 }}>
      {/* Left tree */}
      <div style={{ width: 300, flex: "none", borderRight: "1px solid var(--border-subtle)", display: "flex", flexDirection: "column", background: "var(--bg-surface)" }}>
        <div style={{ padding: 12, borderBottom: "1px solid var(--border-subtle)" }}>
          <div className="input" style={{ display: "flex", alignItems: "center", gap: 6, height: 28 }}>
            <Icons.Search size={12} style={{ color: "var(--fg-mute)" }}/>
            <span style={{ color: "var(--fg-mute)", fontSize: 12 }}>过滤 skill…</span>
          </div>
        </div>
        <div style={{ flex: 1, overflow: "auto", padding: 8 }}>
          <TreeNode icon={<Icons.FolderOpen size={13}/>} label="longtaskforagent" expanded chip="14"/>
          <TreeNode icon={<Icons.File size={13}/>} label="using-claude.md" depth={1}/>
          <TreeNode icon={<Icons.File size={13}/>} label="using-opencode.md" depth={1}/>
          <TreeNode icon={<Icons.File size={13}/>} label="long-task-requirements.md" depth={1} active/>
          <TreeNode icon={<Icons.File size={13}/>} label="ucd.md" depth={1}/>
          <TreeNode icon={<Icons.File size={13}/>} label="design.md" depth={1}/>
          <TreeNode icon={<Icons.FolderOpen size={13}/>} label="work/" depth={1} expanded/>
          <TreeNode icon={<Icons.File size={13}/>} label="feature-design.md" depth={2}/>
          <TreeNode icon={<Icons.File size={13}/>} label="tdd.md" depth={2}/>
          <TreeNode icon={<Icons.File size={13}/>} label="feature-st.md" depth={2}/>
          <TreeNode icon={<Icons.File size={13}/>} label="st.md" depth={1}/>
          <TreeNode icon={<Icons.File size={13}/>} label="finalize.md" depth={1}/>
          <TreeNode icon={<Icons.Folder size={13}/>} label="hotfix.md" depth={1}/>
          <div style={{ height: 12 }}/>
          <TreeNode icon={<Icons.FolderOpen size={13}/>} label="harness-classifier" expanded chip="3"/>
          <TreeNode icon={<Icons.File size={13}/>} label="system_prompt.md" depth={1}/>
          <TreeNode icon={<Icons.File size={13}/>} label="taxonomy.yaml" depth={1}/>
        </div>
      </div>

      {/* Markdown preview */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <div style={{ padding: "14px 28px", borderBottom: "1px solid var(--border-subtle)", display: "flex", alignItems: "center", gap: 10 }}>
          <Icons.File size={14} style={{ color: "var(--fg-mute)" }}/>
          <span className="mono" style={{ fontSize: 12.5, color: "var(--fg-dim)" }}>plugins/longtaskforagent/skills/long-task-requirements/</span>
          <span className="mono" style={{ fontSize: 12.5, color: "var(--fg)", fontWeight: 500 }}>SKILL.md</span>
          <span className="chip outline" style={{ marginLeft: 8 }}>read-only</span>
          <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
            <button className="btn ghost sm"><Icons.Copy/></button>
            <button className="btn ghost sm"><Icons.ExternalLink/></button>
          </div>
        </div>
        <div style={{ flex: 1, overflow: "auto", padding: "32px 48px", maxWidth: 860, width: "100%" }}>
          <div style={{ border: "1px solid var(--border-subtle)", borderRadius: 6, background: "var(--bg-inset)", padding: "10px 14px", marginBottom: 24, display: "flex", alignItems: "center", gap: 10 }}>
            <span className="label" style={{ fontSize: 10 }}>frontmatter</span>
            <span className="mono" style={{ fontSize: 11.5, color: "var(--fg-mute)" }}>name · version · deps · model_hint</span>
            <button className="btn ghost sm" style={{ marginLeft: "auto", height: 22 }}>展开<Icons.ChevronDown/></button>
          </div>

          <h1 style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.015em", marginBottom: 8 }}>long-task-requirements</h1>
          <p className="body" style={{ color: "var(--fg-dim)", marginBottom: 20 }}>
            将用户需求提炼为 <span style={{ color: "var(--fg)" }}>ISO/IEC/IEEE 29148</span> 对齐的 SRS 草稿；
            强制调用 <code className="mono" style={{ fontSize: 12, color: "var(--accent-2)", background: "var(--bg-surface-alt)", padding: "1px 6px", borderRadius: 3 }}>AskUserQuestion</code> 以解决 5-Whys 根因中的歧义点。
          </p>

          <h2 style={{ fontSize: 18, fontWeight: 600, marginTop: 28, marginBottom: 10 }}>Steps</h2>
          <ol style={{ paddingLeft: 20, color: "var(--fg)", lineHeight: 1.8, marginBottom: 20 }}>
            <li>读取 workdir 下既有 README / docs 并抽取上下文</li>
            <li>通过 HIL 锁定范围内 / 范围外边界（EXC 条目）</li>
            <li>按痛点 → FR 反向推导，校验无孤立 FR</li>
            <li>输出 <span className="mono" style={{ color: "var(--accent-3)", fontSize: 13 }}>docs/plans/YYYY-MM-DD-&lt;project&gt;-srs.md</span></li>
          </ol>

          <div style={{
            background: "var(--bg-inset)", border: "1px solid var(--border-subtle)", borderRadius: 6,
            padding: "12px 16px", fontFamily: "var(--font-mono)", fontSize: 12.5, lineHeight: 1.7, marginBottom: 24
          }}>
            <div style={{ color: "var(--code-com)" }}># example tool call</div>
            <div><span style={{ color: "var(--code-kw)" }}>await</span> <span style={{ color: "var(--code-fn)" }}>AskUserQuestion</span>(</div>
            <div style={{ paddingLeft: 16 }}>kind=<span style={{ color: "var(--code-str)" }}>"single_select"</span>,</div>
            <div style={{ paddingLeft: 16 }}>question=<span style={{ color: "var(--code-str)" }}>"选择延期的 FR"</span>,</div>
            <div style={{ paddingLeft: 16 }}>options=[...],</div>
            <div>)</div>
          </div>
        </div>
      </div>
    </div>
  </PageFrame>
);

window.PromptsAndSkillsPage = PromptsAndSkillsPage;
