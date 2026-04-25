/**
 * usePauseScrollOnInteraction —— 用户向上滚 → 暂停 auto-scroll-to-bottom
 *
 * Traces §Interface Contract `usePauseScrollOnInteraction` ·
 *        §Test Inventory T35 ·
 *        §VRC auto-scroll-indicator。
 */
import { useCallback, useState } from "react";

export interface UsePauseScrollResult {
  paused: boolean;
  resume: () => void;
  onWheel: (deltaY: number) => void;
}

export function usePauseScrollOnInteraction(): UsePauseScrollResult {
  const [paused, setPaused] = useState<boolean>(false);
  const resume = useCallback(() => setPaused(false), []);
  const onWheel = useCallback((deltaY: number) => {
    if (deltaY < 0) setPaused(true);
  }, []);
  return { paused, resume, onWheel };
}
