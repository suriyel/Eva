/* global PageFrame, Icons */

const SettingsSection = ({ title, desc, children, footer }) => (
  <div className="card" style={{ padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
    <div>
      <div className="h3">{title}</div>
      {desc && <div className="small" style={{ marginTop: 4, lineHeight: 1.5 }}>{desc}</div>}
    </div>
    {children}
    {footer && <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, paddingTop: 12, borderTop: "1px solid var(--border-subtle)" }}>{footer}</div>}
  </div>
);

const FormRow = ({ label, hint, children, width = 320 }) => (
  <div style={{ display: "flex", alignItems: "flex-start", gap: 24 }}>
    <div style={{ width: 200, paddingTop: 6 }}>
      <div className="label">{label}</div>
      {hint && <div className="small" style={{ fontSize: 11.5, marginTop: 4 }}>{hint}</div>}
    </div>
    <div style={{ flex: 1, maxWidth: width, minWidth: 0 }}>{children}</div>
  </div>
);

const Select = ({ value, right }) => (
  <div className="input" style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
    <span style={{ flex: 1, fontSize: 13 }}>{value}</span>
    {right}
    <Icons.ChevronDown size={13} style={{ color: "var(--fg-mute)" }}/>
  </div>
);

const MaskedInput = ({ value }) => (
  <div className="input" style={{ display: "flex", alignItems: "center", gap: 8, padding: 0, overflow: "hidden" }}>
    <div style={{ flex: 1, padding: "0 12px", fontFamily: "var(--font-mono)", fontSize: 12.5, color: "var(--fg)" }}>
      {value}
    </div>
    <button className="btn ghost sm" style={{ height: "100%", borderRadius: 0, borderLeft: "1px solid var(--border)" }}>
      <Icons.Eye size={12}/>显示
    </button>
  </div>
);

const SystemSettingsPage = () => {
  const tabs = [
    { id: "model", label: "模型与 Provider", icon: <Icons.Cpu size={14}/> },
    { id: "auth", label: "API Key 与认证", icon: <Icons.Power size={14}/> },
    { id: "classifier", label: "Classifier", icon: <Icons.Zap size={14}/> },
    { id: "mcp", label: "全局 MCP", icon: <Icons.Terminal size={14}/> },
    { id: "ui", label: "界面偏好", icon: <Icons.Settings size={14}/> },
  ];
  return (
    <PageFrame active="settings" title="设置">
      <div style={{ display: "flex", gap: 24, padding: 24, maxWidth: 1280, margin: "0 auto" }}>
        <div style={{ width: 200, flex: "none" }}>
          <div className="label" style={{ padding: "0 12px 8px" }}>配置分组</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {tabs.map((t, i) => (
              <div key={t.id} className={`vtab ${i === 0 ? "active" : ""}`}>
                <span style={{ color: i === 0 ? "var(--accent)" : "var(--fg-mute)", display: "flex" }}>{t.icon}</span>
                {t.label}
              </div>
            ))}
          </div>
        </div>

        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 20, minWidth: 0 }}>
          <SettingsSection
            title="Run 默认模型"
            desc="用于未被 per-skill / per-ticket 覆写规则匹配的票据。应用于 claude 与 opencode 两类工具。"
            footer={<><button className="btn ghost sm">重置</button><button className="btn primary sm"><Icons.Save/>保存</button></>}
          >
            <FormRow label="Claude Code 默认" hint="Anthropic sonnet / opus / haiku">
              <Select value="claude-sonnet-4.5 · balanced" right={<span className="chip code" style={{ height: 18, fontSize: 10 }}>anthropic</span>}/>
            </FormRow>
            <FormRow label="OpenCode Provider 默认" hint="OpenAI-compatible endpoint">
              <Select value="glm-4.6 · via bigmodel.cn" right={<span className="chip code" style={{ height: 18, fontSize: 10, color: "var(--accent-3)" }}>glm</span>}/>
            </FormRow>
            <FormRow label="上下文预算" hint="超出后触发 context_overflow 重试">
              <div style={{ display: "flex", gap: 8 }}>
                <input className="input" defaultValue="180000" style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}/>
                <span className="chip outline">tokens</span>
              </div>
            </FormRow>
          </SettingsSection>

          <SettingsSection
            title="Per-Skill 模型覆写规则"
            desc="匹配优先级高于默认模型。匹配顺序自上而下，首个命中即停。"
          >
            <div style={{ border: "1px solid var(--border-subtle)", borderRadius: 6, overflow: "hidden" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 100px 1fr 32px", padding: "10px 14px", background: "var(--bg-surface-alt)", borderBottom: "1px solid var(--border-subtle)" }}>
                <div className="label">Skill 匹配</div>
                <div className="label">工具</div>
                <div className="label">模型</div>
                <div/>
              </div>
              {[
                { skill: "long-task-requirements", tool: "claude", model: "opus-4.7" },
                { skill: "work/tdd-*", tool: "claude", model: "sonnet-4.5" },
                { skill: "classifier/*", tool: "opencode", model: "glm-4.6" },
              ].map((r, i) => (
                <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr 100px 1fr 32px", padding: "10px 14px", borderBottom: i < 2 ? "1px solid var(--border-subtle)" : "none", alignItems: "center", background: i % 2 ? "var(--bg-surface-alt)" : "transparent" }}>
                  <span className="mono" style={{ fontSize: 12.5, color: "var(--fg)" }}>{r.skill}</span>
                  <span className="chip code" style={{ height: 18, fontSize: 10, width: "fit-content", color: r.tool === "claude" ? "#D2A8FF" : "var(--accent-3)" }}>{r.tool}</span>
                  <span className="mono" style={{ fontSize: 12.5, color: "var(--accent-2)" }}>{r.model}</span>
                  <button className="btn ghost icon sm" style={{ width: 24, height: 24 }}><Icons.MoreH/></button>
                </div>
              ))}
            </div>
            <button className="btn secondary sm" style={{ width: "fit-content" }}><Icons.Plus/>新增规则</button>
          </SettingsSection>

          <SettingsSection
            title="API Key"
            desc={<>通过平台 keyring 存储 · 不写入 <span className="mono" style={{ color: "var(--accent-2)" }}>~/.claude/</span> 或工作目录。</>}
          >
            <FormRow label="Anthropic API Key"><MaskedInput value={"sk-ant-••••••••••••••••••••fX9A"}/></FormRow>
            <FormRow label="OpenCode Provider Key"><MaskedInput value={"glm-••••••••••••••••••••K2"}/></FormRow>
            <FormRow label="测试连接" hint="curl GET $base_url/v1/models">
              <button className="btn secondary sm"><Icons.RefreshCw/>测试 2 个 Provider</button>
            </FormRow>
          </SettingsSection>
        </div>
      </div>
    </PageFrame>
  );
};

window.SystemSettingsPage = SystemSettingsPage;
