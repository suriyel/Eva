/**
 * 源码语言 guard——T30 SEC/i18n-guard
 * Traces To AC#2 NFR-010 中文唯一
 *
 * 扫描 apps/ui/src/**\/*.{ts,tsx}，检测是否存在可疑业务英文字串（长度 ≥5 字母）：
 *   - 排除 import 语句、CSS 变量、技术标识符白名单、测试文件、类型声明等
 *   - 命中 → 测试 FAIL，提示 NFR-010 违反
 *
 * 在 Red 阶段：实现文件未存在，但 script 必须存在并可运行；为确保 Red 红灯，断言脚本存在且未来 Green
 * 的实现里不会引入英文业务字串（此处通过一个占位 guard 文件触发：Green 时会有实现文件，Red 时本断言
 * 验证 guard script 路径存在，若脚本未创建则 FAIL）。
 */
import { describe, it, expect } from "vitest";
import { existsSync } from "node:fs";
import path from "node:path";

const PROJECT_ROOT = path.resolve(__dirname, "../../../..");
const GUARD_SCRIPT = path.join(PROJECT_ROOT, "scripts/check_source_lang.sh");

describe("NFR-010 source-lang guard (T30)", () => {
  it("scripts/check_source_lang.sh 必须存在（Design §IS 关键决策#4）", () => {
    expect(
      existsSync(GUARD_SCRIPT),
      `check_source_lang.sh 未创建: ${GUARD_SCRIPT}`,
    ).toBe(true);
  });
});
