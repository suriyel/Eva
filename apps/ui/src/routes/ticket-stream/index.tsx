/**
 * TicketStreamPage —— /ticket-stream 路由：三栏 layout（list / event-tree / inspector）
 *
 * Traces §Interface Contract `TicketStreamPage` ·
 *        §Test Inventory T23 / T24 / T27 / T35 / T36 / T43 / T25 / T26 ·
 *        §Visual Rendering Contract three-column layout / auto-scroll / inline search ·
 *        SRS FR-034 AC-1（筛选）+ AC-2（折叠展开）+ NFR-002 + IFR-007。
 *
 * 调用链：
 *   useTicketStreamFilters() → URL filters →
 *   useQuery('/api/tickets?…filters') →
 *   useQuery('/api/tickets/:id/stream') 历史 →
 *   useWs('/ws/stream/:id') 增量 →
 *   EventTree (@tanstack/react-virtual) 渲染。
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useWs } from "@/ws/use-ws";
import { Icons } from "@/components/icons";
import { resolveApiBaseUrl } from "@/api/client";
import { useCurrentRunId } from "@/api/routes/run-current";
import { useTicketStreamFilters, type TicketFilters } from "./use-filters";
import { EventTree, type StreamEventLike } from "./components/event-tree";

interface TicketDto {
  id: string;
  state: string;
  tool: string;
  skill: string;
  events?: number;
  parent?: string;
  run_id?: string;
}

/**
 * F24 B2 — buildTicketsUrl
 *
 * Returns ``null`` when no run_id can be derived; callers MUST treat null as
 * "skip fetch" so we don't spam ``GET /api/tickets`` with missing run_id and
 * inflate 400 responses.
 */
function buildTicketsUrl(filters: TicketFilters): string | null {
  const runId = filters.run_id;
  if (!runId) return null;
  const u = new URLSearchParams();
  if (filters.state) u.set("state", filters.state);
  if (filters.tool) u.set("tool", filters.tool);
  u.set("run_id", runId);
  if (filters.parent) u.set("parent", filters.parent);
  const qs = u.toString();
  return `${resolveApiBaseUrl()}/api/tickets${qs ? `?${qs}` : ""}`;
}

function ticketCardStyle(isSelected: boolean): React.CSSProperties {
  return {
    padding: "10px 12px",
    borderRadius: 6,
    background: isSelected ? "var(--bg-active)" : "var(--bg-surface)",
    border: `1px solid ${isSelected ? "var(--accent)" : "var(--border-subtle)"}`,
    cursor: "pointer",
    display: "flex",
    flexDirection: "column",
    gap: 4,
  };
}

export function TicketStreamPage(): React.ReactElement {
  const { filters, setFilter } = useTicketStreamFilters();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedTicketId = searchParams.get("ticket");
  // F24 B2 — currentRunId fallback so URL params or current-run hook can
  // populate ``filters.run_id`` even when the user hasn't manually set it.
  const fallbackRunId = useCurrentRunId();
  const effectiveFilters: TicketFilters = React.useMemo(
    () => ({
      ...filters,
      run_id: filters.run_id ?? fallbackRunId ?? undefined,
    }),
    [filters, fallbackRunId],
  );
  const ticketsUrl = buildTicketsUrl(effectiveFilters);
  const ticketsQ = useQuery<TicketDto[]>({
    queryKey: ["GET", "/api/tickets", effectiveFilters],
    enabled: ticketsUrl !== null,
    queryFn: async () => {
      if (!ticketsUrl) return [];
      const resp = await fetch(ticketsUrl);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const text = await resp.text();
      return text ? (JSON.parse(text) as TicketDto[]) : [];
    },
  });

  const tickets = ticketsQ.data ?? [];
  const activeTicketId = selectedTicketId ?? tickets[0]?.id ?? null;

  const streamHistQ = useQuery<StreamEventLike[]>({
    queryKey: ["GET", "/api/tickets/:id/stream", activeTicketId],
    enabled: !!activeTicketId,
    queryFn: async () => {
      if (!activeTicketId) return [];
      const resp = await fetch(`${resolveApiBaseUrl()}/api/tickets/${activeTicketId}/stream`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const text = await resp.text();
      return text ? (JSON.parse(text) as StreamEventLike[]) : [];
    },
  });

  const [liveEvents, setLiveEvents] = React.useState<StreamEventLike[]>([]);
  const [pausedByUser, setPausedByUser] = React.useState<boolean>(false);
  const [searchQuery, setSearchQuery] = React.useState<string>("");
  const [selectedEvent, setSelectedEvent] = React.useState<StreamEventLike | null>(null);
  const searchInputRef = React.useRef<HTMLInputElement | null>(null);

  // reset live events when ticket switches
  React.useEffect(() => {
    setLiveEvents([]);
    setSelectedEvent(null);
  }, [activeTicketId]);

  const onWsEvent = React.useCallback((ev: { kind: string; payload?: unknown }) => {
    if (!ev || typeof ev.kind !== "string") return;
    if (ev.kind !== "stream_event") return;
    const p = ev.payload as StreamEventLike | undefined;
    if (!p || typeof p.seq !== "number") return;
    setLiveEvents((prev) => [...prev, p]);
  }, []);

  const wsChannel = activeTicketId ? `/ws/stream/${activeTicketId}` : "/ws/stream/_idle";
  useWs(wsChannel, onWsEvent);

  // Ctrl/Cmd+F → focus inline search; preventDefault native find
  React.useEffect(() => {
    const handler = (e: KeyboardEvent): void => {
      if ((e.metaKey || e.ctrlKey) && (e.key === "f" || e.key === "F")) {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const onWheel = React.useCallback((e: React.WheelEvent<HTMLDivElement>) => {
    if (e.deltaY < 0) {
      setPausedByUser(true);
    }
  }, []);

  const allEvents = React.useMemo(() => {
    const hist = streamHistQ.data ?? [];
    return [...hist, ...liveEvents];
  }, [streamHistQ.data, liveEvents]);

  const searchHits = React.useMemo<Set<number>>(() => {
    if (!searchQuery) return new Set<number>();
    const out = new Set<number>();
    const q = searchQuery.toLowerCase();
    allEvents.forEach((ev, i) => {
      const text = JSON.stringify(ev.payload ?? "").toLowerCase();
      if (text.includes(q)) out.add(i);
    });
    return out;
  }, [allEvents, searchQuery]);

  return (
    <div
      data-component="ticket-stream-page"
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        minHeight: 0,
      }}
    >
      <div
        data-component="ticket-stream-filter-bar"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 16px",
          borderBottom: "1px solid var(--border-subtle)",
        }}
      >
        <Icons.Filter size={14} />
        <button
          data-filter="state"
          type="button"
          onClick={() => setFilter("state", filters.state === "running" ? undefined : "running")}
          style={{
            padding: "4px 10px",
            borderRadius: 4,
            background: filters.state === "running" ? "var(--bg-active)" : "transparent",
            border: `1px solid ${filters.state === "running" ? "var(--accent)" : "var(--border-subtle)"}`,
            color: "var(--fg)",
            fontSize: 12,
            cursor: "pointer",
          }}
        >
          state: running
        </button>
        <button
          data-filter="tool"
          type="button"
          onClick={() => setFilter("tool", filters.tool === "claude" ? undefined : "claude")}
          style={{
            padding: "4px 10px",
            borderRadius: 4,
            background: filters.tool === "claude" ? "var(--bg-active)" : "transparent",
            border: `1px solid ${filters.tool === "claude" ? "var(--accent)" : "var(--border-subtle)"}`,
            color: "var(--fg)",
            fontSize: 12,
            cursor: "pointer",
          }}
        >
          tool: claude
        </button>
        <input
          ref={searchInputRef}
          data-testid="inline-search"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Ctrl/Cmd+F 内联搜索"
          style={{
            marginLeft: "auto",
            padding: "4px 10px",
            width: 220,
            borderRadius: 4,
            background: "var(--bg-surface)",
            border: "1px solid var(--border-subtle)",
            color: "var(--fg)",
            fontSize: 12,
          }}
        />
        <span
          data-testid="auto-scroll-indicator"
          style={{
            padding: "2px 10px",
            fontSize: 11,
            color: pausedByUser ? "var(--fg-mute)" : "var(--state-running)",
            border: `1px solid ${pausedByUser ? "var(--border-subtle)" : "var(--state-running)"}`,
            borderRadius: 999,
            cursor: "pointer",
          }}
          onClick={() => setPausedByUser(false)}
        >
          {pausedByUser ? "已暂停 · 点击恢复" : "Live · auto-scroll"}
        </span>
      </div>
      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        <div
          data-component="ticket-list"
          style={{
            width: 320,
            flex: "none",
            borderRight: "1px solid var(--border-subtle)",
            overflowY: "auto",
            padding: 8,
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          {tickets.map((t) => (
            <div
              key={t.id}
              data-component="ticket-card"
              data-tool={t.tool}
              data-state={t.state}
              data-ticket-id={t.id}
              onClick={() => {
                const next = new URLSearchParams(searchParams);
                next.set("ticket", t.id);
                setSearchParams(next, { replace: true });
              }}
              style={ticketCardStyle(t.id === activeTicketId)}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span className="mono" style={{ fontSize: 11, color: "var(--fg-mute)" }}>
                  #{t.id}
                </span>
                <span
                  style={{
                    fontSize: 10.5,
                    color: "var(--fg-dim)",
                    padding: "1px 6px",
                    borderRadius: 4,
                    border: "1px solid var(--border-subtle)",
                  }}
                >
                  {t.tool}
                </span>
              </div>
              <div style={{ fontSize: 12, color: "var(--fg)" }}>{t.skill}</div>
              <div style={{ fontSize: 11, color: "var(--fg-mute)" }}>{t.state}</div>
            </div>
          ))}
        </div>
        <EventTree
          events={allEvents}
          onWheel={onWheel}
          searchHits={searchHits}
          onSelect={(ev) => setSelectedEvent(ev)}
        />
        <div
          data-component="event-inspector"
          style={{
            width: 340,
            flex: "none",
            borderLeft: "1px solid var(--border-subtle)",
            overflowY: "auto",
            padding: 12,
            background: "var(--bg-surface)",
            fontSize: 12,
          }}
        >
          {selectedEvent ? (
            <pre
              style={{
                whiteSpace: "pre-wrap",
                wordBreak: "break-all",
                fontFamily: "var(--font-mono)",
                color: "var(--fg)",
              }}
            >
              {JSON.stringify(selectedEvent, null, 2)}
            </pre>
          ) : (
            <div style={{ color: "var(--fg-mute)" }}>选中事件以查看详情</div>
          )}
        </div>
      </div>
    </div>
  );
}
