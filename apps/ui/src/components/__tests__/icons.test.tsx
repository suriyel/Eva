/**
 * Icons 测试——T38 FUNC/happy
 * Traces To §IC Icons postcondition（prototype Icons.jsx 40+ 同名键；stroke 1.75；size 16）
 *
 * SRS Trace: NFR-011（HIL 控件标注基座义务 —— F12 提供 Icons 库供 F21 HILCard
 *   在 "单选/多选/自由文本" 标签附近渲染图标；F12 职责至"图标键名稳定 + stroke/size 正确"）
 */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Icons } from "@/components/icons";

describe("Icons", () => {
  it("T38 Icons.Home 渲染为 <svg>，stroke-width=1.75，width=height=16", () => {
    const Home = Icons.Home;
    expect(typeof Home).toBe("function");
    const { container } = render(<Home />);
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg!.getAttribute("stroke-width")).toBe("1.75");
    expect(svg!.getAttribute("width")).toBe("16");
    expect(svg!.getAttribute("height")).toBe("16");
  });

  it("T38 Icons 集合含 prototype 关键键（Home/Inbox/Zap）", () => {
    expect(Icons).toHaveProperty("Home");
    expect(Icons).toHaveProperty("Inbox");
    expect(Icons).toHaveProperty("Zap");
  });
});
