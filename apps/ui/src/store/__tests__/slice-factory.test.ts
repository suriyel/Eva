/**
 * createSlice 测试——T13 FUNC/happy · T14 FUNC/error
 * Traces To §IC createSlice Raises（重名）
 */
import { describe, it, expect } from "vitest";
import { createSlice, __resetStoreRegistryForTests } from "@/store/slice-factory";

describe("createSlice", () => {
  it("T13 创建 ui slice——初始 collapsed=false，toggle 翻转后为 true", () => {
    __resetStoreRegistryForTests();
    const useUi = createSlice<{ collapsed: boolean; toggle: () => void }>(
      "ui-t13",
      (set) => ({
        collapsed: false,
        toggle: () => set((s) => ({ collapsed: !s.collapsed })),
      }),
    );
    // Zustand hook 直接调用 (.getState 暴露 action)
    expect(useUi.getState().collapsed).toBe(false);
    useUi.getState().toggle();
    expect(useUi.getState().collapsed).toBe(true);
  });

  it("T14 同名 slice 创建两次——第 2 次抛 Error 且包含 name", () => {
    __resetStoreRegistryForTests();
    createSlice("dup", () => ({ v: 1 }));
    expect(() => createSlice("dup", () => ({ v: 2 }))).toThrow(/dup/);
  });
});
