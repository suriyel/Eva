/**
 * useInlineSearch —— Ctrl/Cmd+F 命中 hook（§Interface Contract `useInlineSearch`）
 *
 * Traces §VRC inline search · T36（preventDefault + 高亮 hits[]）。
 *
 * 使用：
 *   const { query, setQuery, hits } = useInlineSearch(events);
 *   把 hits 传到 EventTree 的 searchHits 集合做行高亮。
 */
import { useEffect, useMemo, useRef, useState } from "react";
import type { StreamEventLike } from "./components/event-tree";

export interface UseInlineSearchResult {
  query: string;
  setQuery: (q: string) => void;
  hits: number[];
  searchInputRef: React.RefObject<HTMLInputElement>;
}

export function useInlineSearch(events: StreamEventLike[]): UseInlineSearchResult {
  const [query, setQuery] = useState<string>("");
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent): void => {
      if ((e.metaKey || e.ctrlKey) && (e.key === "f" || e.key === "F")) {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const hits = useMemo<number[]>(() => {
    if (!query) return [];
    const q = query.toLowerCase();
    const out: number[] = [];
    events.forEach((ev, i) => {
      const text = JSON.stringify(ev.payload ?? "").toLowerCase();
      if (text.includes(q)) out.push(i);
    });
    return out;
  }, [events, query]);

  return { query, setQuery, hits, searchInputRef };
}
