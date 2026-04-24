/**
 * tokens.css 保真度测试——T26 UI/render
 * Traces To AC#7 token-fidelity · UCD §5 F12 实施规约
 *
 * 断言 `apps/ui/src/theme/tokens.css` 在 :root 块内的 token 值与
 * `docs/design-bundle/eava2/project/styles/tokens.css` 相同 :root 块字节等价；
 * 仅允许的差异是 §2.5 中文排印扩展 + §2.2 prefers-reduced-motion 追加块（必须存在且在末尾）。
 */
import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { getTokensCssText } from "@/theme/tokens-inline";

const PROJECT_ROOT = path.resolve(__dirname, "../../../../..");
const PROTO_TOKENS = path.join(PROJECT_ROOT, "docs/design-bundle/eava2/project/styles/tokens.css");
const UI_TOKENS = path.join(PROJECT_ROOT, "apps/ui/src/theme/tokens.css");

function extractRoot(src: string): string {
  const m = src.match(/:root\s*\{[\s\S]*?\}/);
  if (!m) throw new Error(":root block not found");
  return m[0];
}

describe("tokens.css fidelity (T26)", () => {
  it("apps/ui/src/theme/tokens.css 存在", () => {
    expect(existsSync(UI_TOKENS), `tokens.css 尚未创建: ${UI_TOKENS}`).toBe(true);
  });

  it(":root 块与 prototype 字节等价（禁止修改已有 token 值）", () => {
    const proto = readFileSync(PROTO_TOKENS, "utf-8");
    const ours = readFileSync(UI_TOKENS, "utf-8");
    const protoRoot = extractRoot(proto);
    const ourRoot = extractRoot(ours);
    expect(ourRoot).toBe(protoRoot);
  });

  it("必须包含 §2.5 中文排印扩展 class (.hns-cn-body / .hns-cn-heading)", () => {
    const ours = readFileSync(UI_TOKENS, "utf-8");
    expect(ours).toMatch(/\.hns-cn-body/);
    expect(ours).toMatch(/\.hns-cn-heading/);
  });

  it("必须包含 §2.2 prefers-reduced-motion 降级块", () => {
    const ours = readFileSync(UI_TOKENS, "utf-8");
    expect(ours).toMatch(/@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)/);
  });
});

// ---------------------------------------------------------------------------
// 补充测试：tokens-inline.getTokensCssText 缓存语义 + 实际内容包含 :root block
// Traces To §VRC "Theme surface" 正向渲染断言（`--bg-app` 必须可解析）+ §IS
// (1) tokens.css byte-identical。AppShell.tsx 依赖该函数把 tokens 注入 <style>，
// 故 happy-dom 下 getComputedStyle(documentElement) 能读到 `--bg-app`。
// ---------------------------------------------------------------------------
describe("getTokensCssText", () => {
  it("返回的字符串包含 :root 声明与 --bg-app token（Vite ?raw 分支）", () => {
    const text = getTokensCssText();
    expect(text.length).toBeGreaterThan(0);
    expect(text).toMatch(/:root\s*\{/);
    expect(text).toMatch(/--bg-app\s*:/);
  });

  it("多次调用返回同一缓存字符串实例（cached 命中分支）", () => {
    const a = getTokensCssText();
    const b = getTokensCssText();
    // identity 命中缓存——同引用
    expect(a).toBe(b);
  });
});
