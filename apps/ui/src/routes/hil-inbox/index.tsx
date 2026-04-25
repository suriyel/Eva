/**
 * HilInboxPage —— /hil 路由首页
 *
 * Traces §Interface Contract `HilInboxPage` ·
 *        §Test Inventory T03 / T04 / T18 / T28 / T45 ·
 *        SRS FR-031 AC-1（3 卡片）+ AC-2（answered 状态机）·
 *        sequenceDiagram HIL 提交链。
 *
 * 调用链：useQuery('/api/tickets?state=hil_waiting') → 列出 N 张 hil-card；
 *        useWs('/ws/hil', onEvent) → 增量 HilQuestionOpened 新增 hil-card；
 *        HilAnswerAccepted → 卡片 answered=true。
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { useWs } from "@/ws/use-ws";
import { resolveApiBaseUrl } from "@/api/client";
import { HILCard, type HilCardVariant, type HilOption } from "./components/hil-card";
import { deriveHilControl, type HilQuestionLike } from "./derive-control";

interface HilQuestionDto {
  id: string;
  question: string;
  multi_select: boolean;
  options: HilOption[];
  allow_freeform: boolean;
}

interface HilTicketDto {
  id: string;
  state: string;
  questions: HilQuestionDto[];
  phase?: string;
  phase_color?: string;
}

interface HilCardEntry {
  ticketId: string;
  questionId: string;
  variant: HilCardVariant;
  question: string;
  options: HilOption[];
  phase: string;
  phaseColor?: string;
  answered: boolean;
}

function safeDeriveVariant(q: HilQuestionLike): HilCardVariant | null {
  try {
    return deriveHilControl(q);
  } catch {
    return null;
  }
}

function ticketsToEntries(tickets: HilTicketDto[]): HilCardEntry[] {
  const out: HilCardEntry[] = [];
  for (const t of tickets) {
    if (!t || !Array.isArray(t.questions) || t.questions.length === 0) continue;
    const q = t.questions[0];
    const variant = safeDeriveVariant(q);
    if (!variant) continue;
    out.push({
      ticketId: t.id,
      questionId: q.id,
      variant,
      question: q.question ?? "",
      options: q.options ?? [],
      phase: t.phase ?? "Design",
      phaseColor: t.phase_color,
      answered: false,
    });
  }
  return out;
}

export function HilInboxPage(): React.ReactElement {
  const tickets = useQuery<HilTicketDto[]>({
    queryKey: ["GET", "/api/tickets?state=hil_waiting"],
    queryFn: async () => {
      const resp = await fetch(`${resolveApiBaseUrl()}/api/tickets?state=hil_waiting`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const text = await resp.text();
      return text ? (JSON.parse(text) as HilTicketDto[]) : [];
    },
  });

  const [extraEntries, setExtraEntries] = React.useState<HilCardEntry[]>([]);
  const [answeredQuestions, setAnsweredQuestions] = React.useState<Set<string>>(new Set());

  const onWsEvent = React.useCallback((ev: { kind: string; payload?: unknown }) => {
    if (!ev || typeof ev.kind !== "string") return;
    if (ev.kind === "hil_question_opened") {
      const p = ev.payload as { ticket_id?: string; questions?: HilQuestionDto[] } | undefined;
      if (!p || typeof p.ticket_id !== "string" || !Array.isArray(p.questions)) return;
      const newEntries = ticketsToEntries([
        {
          id: p.ticket_id,
          state: "hil_waiting",
          questions: p.questions,
        },
      ]);
      if (newEntries.length > 0) {
        setExtraEntries((prev) => [...prev, ...newEntries]);
      }
      return;
    }
    if (ev.kind === "hil_answer_accepted") {
      const p = ev.payload as { question_id?: string } | undefined;
      if (p && typeof p.question_id === "string") {
        setAnsweredQuestions((prev) => {
          const next = new Set(prev);
          next.add(p.question_id as string);
          return next;
        });
      }
      return;
    }
    // unknown kind: silent (T45)
  }, []);

  useWs("/ws/hil", onWsEvent);

  const baseEntries = React.useMemo(
    () => ticketsToEntries(tickets.data ?? []),
    [tickets.data],
  );
  const allEntries = React.useMemo(
    () => [...baseEntries, ...extraEntries],
    [baseEntries, extraEntries],
  );
  // dedupe by questionId
  const dedupedEntries = React.useMemo(() => {
    const seen = new Set<string>();
    const out: HilCardEntry[] = [];
    for (const e of allEntries) {
      if (seen.has(e.questionId)) continue;
      seen.add(e.questionId);
      out.push({ ...e, answered: answeredQuestions.has(e.questionId) });
    }
    return out;
  }, [allEntries, answeredQuestions]);

  const isLoading = tickets.isLoading;
  const isEmpty = !isLoading && dedupedEntries.length === 0;

  return (
    <div data-component="hil-inbox-page" style={{ padding: 24 }}>
      {isEmpty && (
        <div
          data-testid="hil-empty"
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: 64,
            color: "var(--fg-mute)",
          }}
        >
          <div style={{ fontSize: 32, marginBottom: 12 }}>💤</div>
          <div style={{ fontSize: 16, fontWeight: 500, color: "var(--fg-dim)" }}>
            无待答 HIL
          </div>
        </div>
      )}
      {!isEmpty && (
        <div
          data-component="hil-card-list"
          style={{ display: "flex", flexDirection: "column", gap: 16 }}
        >
          {dedupedEntries.map((e) => (
            <HILCard
              key={e.questionId}
              ticketId={e.ticketId}
              questionId={e.questionId}
              variant={e.variant}
              question={e.question}
              options={e.options}
              phase={e.phase}
              phaseColor={e.phaseColor}
              answered={e.answered}
            />
          ))}
        </div>
      )}
    </div>
  );
}
