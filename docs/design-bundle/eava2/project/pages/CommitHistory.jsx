/* global PageFrame, Icons */

const commits = [
  { sha: "de507b2", msg: "docs: add Harness SRS (Lite track) with 50 FR + 10 NFR", author: "Harness", time: "2m ago", feature: "feature-01", stat: { a: 848, d: 0 }, active: true },
  { sha: "8f3a19c", msg: "feat(ticket): SQLite schema + JSONL audit log writer", author: "Harness", time: "18m ago", feature: "feature-01", stat: { a: 420, d: 12 } },
  { sha: "b0c4e73", msg: "feat(hil): pty capture for AskUserQuestion stream-json", author: "Harness", time: "41m ago", feature: "feature-02", stat: { a: 287, d: 4 } },
  { sha: "2fd88a0", msg: "test(ticket): edge cases for retry backoff classifier", author: "Harness", time: "1h ago", feature: "feature-01", stat: { a: 156, d: 3 } },
  { sha: "1a9b2c4", msg: "chore: init .harness-workdir isolation layout", author: "Harness", time: "2h ago", feature: null, stat: { a: 72, d: 0 } },
  { sha: "07e1e5d", msg: "scaffold: pyproject + PyWebView entry + PyInstaller spec", author: "Harness", time: "2h ago", feature: null, stat: { a: 312, d: 0 } },
];

const DiffLine = ({ kind, no, no2, text }) => {
  const map = {
    "+": { bg: "var(--diff-add-bg)", fg: "var(--diff-add-fg)", gut: "var(--diff-add-gut)", sign: "+" },
    "-": { bg: "var(--diff-del-bg)", fg: "var(--diff-del-fg)", gut: "var(--diff-del-gut)", sign: "−" },
    " ": { bg: "transparent", fg: "var(--fg-dim)", gut: "transparent", sign: " " },
    "@": { bg: "var(--bg-surface-alt)", fg: "var(--accent-2)", gut: "var(--bg-surface-alt)", sign: "@" },
  };
  const m = map[kind];
  return (
    <div style={{ display: "flex", fontFamily: "var(--font-mono)", fontSize: 12.5, lineHeight: "22px", background: m.bg }}>
      <div style={{ width: 44, textAlign: "right", paddingRight: 8, color: "var(--fg-faint)", background: m.gut, flex: "none", userSelect: "none" }}>{no}</div>
      <div style={{ width: 44, textAlign: "right", paddingRight: 8, color: "var(--fg-faint)", background: m.gut, flex: "none", userSelect: "none" }}>{no2}</div>
      <div style={{ width: 20, textAlign: "center", color: m.fg, background: m.gut, flex: "none" }}>{m.sign}</div>
      <div style={{ flex: 1, paddingLeft: 12, color: kind === "@" ? "var(--accent-2)" : kind === " " ? "var(--fg-dim)" : m.fg, whiteSpace: "pre" }}>{text}</div>
    </div>
  );
};

const CommitRow = ({ c }) => (
  <div style={{
    display: "flex", flexDirection: "column", gap: 4, padding: "14px 16px",
    background: c.active ? "var(--bg-active)" : "transparent",
    borderLeft: c.active ? "3px solid var(--accent)" : "3px solid transparent",
    borderBottom: "1px solid var(--border-subtle)", cursor: "pointer",
  }}>
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <Icons.GitCommit size={12} style={{ color: c.active ? "var(--accent)" : "var(--fg-mute)" }}/>
      <span className="mono" style={{ fontSize: 11.5, color: "var(--accent-3)", fontWeight: 600 }}>{c.sha}</span>
      <span style={{ fontSize: 13, color: "var(--fg)", fontWeight: 500, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.msg}</span>
    </div>
    <div style={{ display: "flex", alignItems: "center", gap: 8, paddingLeft: 20 }}>
      <span className="small" style={{ fontSize: 11 }}>{c.author} · {c.time}</span>
      {c.feature && <span className="chip outline" style={{ height: 17, fontSize: 10, color: "var(--accent-2)" }}>{c.feature}</span>}
      <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6, fontSize: 10.5, fontFamily: "var(--font-mono)" }}>
        <span style={{ color: "var(--diff-add-fg)" }}>+{c.stat.a}</span>
        <span style={{ color: "var(--diff-del-fg)" }}>−{c.stat.d}</span>
      </span>
    </div>
  </div>
);

const CommitHistoryPage = () => (
  <PageFrame
    active="commits"
    title="提交历史"
    headerRight={
      <>
        <button className="btn secondary sm"><Icons.GitBranch/>main · 6 commits</button>
      </>
    }
  >
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 20px", borderBottom: "1px solid var(--border-subtle)", background: "var(--bg-surface)" }}>
        <span className="chip code" style={{ color: "var(--accent-3)" }}>#run-26.04.21-001</span>
        <button className="btn secondary sm">Feature · 全部<Icons.ChevronDown size={12}/></button>
        <button className="btn secondary sm">时间 · 24h<Icons.ChevronDown size={12}/></button>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
          <span className="small" style={{ fontSize: 11.5 }}>基线 <span className="mono" style={{ color: "var(--fg-mute)" }}>origin/main</span></span>
          <button className="btn ghost sm"><Icons.ExternalLink/>Open in editor</button>
        </div>
      </div>

      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        {/* Commits list */}
        <div style={{ width: 380, flex: "none", borderRight: "1px solid var(--border-subtle)", overflow: "auto", background: "var(--bg-surface)" }}>
          {commits.map(c => <CommitRow key={c.sha} c={c}/>)}
        </div>

        {/* Diff viewer */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, background: "var(--bg-app)" }}>
          {/* Commit header */}
          <div style={{ padding: "16px 24px", borderBottom: "1px solid var(--border-subtle)", background: "var(--bg-surface)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
              <span className="mono" style={{ fontSize: 13, color: "var(--accent-3)", fontWeight: 600 }}>de507b2</span>
              <span style={{ fontSize: 14.5, fontWeight: 600 }}>docs: add Harness SRS (Lite track) with 50 FR + 10 NFR</span>
              <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
                <button className="btn ghost sm"><Icons.Copy/>复制 sha</button>
                <button className="btn ghost sm">side-by-side</button>
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 11.5, color: "var(--fg-dim)" }}>
              <span>Harness · 2m ago</span>
              <span style={{ color: "var(--fg-faint)" }}>·</span>
              <span className="chip outline" style={{ color: "var(--accent-2)" }}>feature-01</span>
              <span style={{ color: "var(--fg-faint)" }}>·</span>
              <span>1 file · <span style={{ color: "var(--diff-add-fg)" }}>+848</span> <span style={{ color: "var(--diff-del-fg)" }}>−0</span></span>
            </div>
          </div>

          {/* File section */}
          <div style={{ flex: 1, overflow: "auto" }}>
            <div style={{ padding: "10px 16px", display: "flex", alignItems: "center", gap: 10, borderBottom: "1px solid var(--border-subtle)", background: "var(--bg-surface-alt)", position: "sticky", top: 0, zIndex: 1 }}>
              <Icons.ChevronDown size={12}/>
              <Icons.FileText size={13} style={{ color: "var(--fg-mute)" }}/>
              <span className="mono" style={{ fontSize: 12.5, color: "var(--fg)" }}>docs/plans/2026-04-21-harness-srs.md</span>
              <span className="chip solid" style={{ color: "var(--diff-add-fg)", background: "rgba(62,207,142,0.1)", borderColor: "rgba(62,207,142,0.25)" }}>+848</span>
              <span className="chip outline">new file</span>
            </div>

            <DiffLine kind="@" no="" no2="" text="@@ -0,0 +1,848 @@ new file mode 100644"/>
            <DiffLine kind="+" no="" no2="1" text="# Harness — 软件需求规约"/>
            <DiffLine kind="+" no="" no2="2" text=""/>
            <DiffLine kind="+" no="" no2="3" text="**日期（Date）**: 2026-04-21"/>
            <DiffLine kind="+" no="" no2="4" text="**状态（Status）**: Approved"/>
            <DiffLine kind="+" no="" no2="5" text="**参照标准**: 对齐 ISO/IEC/IEEE 29148"/>
            <DiffLine kind="+" no="" no2="6" text="**轨道（Track）**: Lite"/>
            <DiffLine kind="+" no="" no2="7" text=""/>
            <DiffLine kind="+" no="" no2="8" text="## 1. 目的与范围"/>
            <DiffLine kind="+" no="" no2="9" text=""/>
            <DiffLine kind="+" no="" no2="10" text="Harness 是一个桌面外部包裹层，用于在单机单用户"/>
            <DiffLine kind="+" no="" no2="11" text="场景下自动编排 longtaskforagent 的 14-skill 管线，"/>
            <DiffLine kind="+" no="" no2="12" text="驱动 Claude Code 与 OpenCode 交互会话。"/>
            <DiffLine kind="+" no="" no2="13" text=""/>
            <DiffLine kind="@" no="" no2="" text="@@ -0,0 +31,12 @@ ### 1.1 范围内（In Scope）"/>
            <DiffLine kind="+" no="" no2="31" text="- 自动循环驱动 14 skill (using / requirements / ucd / design"/>
            <DiffLine kind="+" no="" no2="32" text="  / ats / init / work / quality / feature-st / st / finalize)"/>
            <DiffLine kind="+" no="" no2="33" text="- 两个 ToolAdapter: Claude Code + OpenCode (pty 穿透 + hooks)"/>
            <DiffLine kind="+" no="" no2="34" text="- 票据系统 (SQLite tickets 表 + append-only JSONL audit log)"/>
            <DiffLine kind="+" no="" no2="35" text="- HIL 捕获 + UI 渲染 (single / multi / free_text)"/>
            <DiffLine kind="+" no="" no2="36" text="- 异常分类 + 指数退避自动恢复"/>
            <DiffLine kind="+" no="" no2="37" text=""/>
            <DiffLine kind="@" no="" no2="" text="@@ -0,0 +62,6 @@ ## 3. 干系人与用户画像"/>
            <DiffLine kind="+" no="" no2="62" text="| Persona | Technical Level | Key Needs |"/>
            <DiffLine kind="+" no="" no2="63" text="|---------|----------------|-----------|"/>
            <DiffLine kind="+" no="" no2="64" text="| Harness User | 中-高 | 启动 run / 回答 HIL |"/>
            <div style={{ padding: "20px", textAlign: "center", color: "var(--fg-mute)", borderTop: "1px solid var(--border-subtle)", fontSize: 12 }}>
              <button className="btn secondary sm"><Icons.ChevronDown size={12}/>展开剩余 14 个 hunk · 820 行</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </PageFrame>
);

window.CommitHistoryPage = CommitHistoryPage;
