/**
 * Vite entry — mount AppShell into #root.
 * F21 替换 / · /hil · /stream(改为 /ticket-stream) 三条占位路由为真实页面。
 */
import * as React from "react";
import ReactDOM from "react-dom/client";
import { AppShell, type RouteSpec } from "./app/app-shell";
import { RunOverviewPage } from "./routes/run-overview";
import { HilInboxPage } from "./routes/hil-inbox";
import { TicketStreamPage } from "./routes/ticket-stream";
import "./theme/tokens.css";

const placeholder = (
  <div data-component="route-placeholder" style={{ padding: 24, color: "var(--fg-dim)" }} />
);
const defaultRoutes: RouteSpec[] = [
  { path: "/", nav: "overview", title: "总览", element: <RunOverviewPage /> },
  { path: "/hil", nav: "hil", title: "HIL 待答", element: <HilInboxPage /> },
  { path: "/ticket-stream", nav: "stream", title: "Ticket 流", element: <TicketStreamPage /> },
  // F21 设计 §4.6.2 路由表为 `/ticket-stream`；保留 `/stream` 作为 Sidebar.NAV_ITEMS
  // 的 nav id 同义路径，避免 F12 Sidebar 的 active 高亮回退到 overview。
  { path: "/stream", nav: "stream", title: "Ticket 流", element: <TicketStreamPage /> },
  { path: "/docs", nav: "docs", title: "文档 & ROI", element: placeholder },
  { path: "/process", nav: "process", title: "过程文件", element: placeholder },
  { path: "/commits", nav: "commits", title: "提交历史", element: placeholder },
  { path: "/skills", nav: "skills", title: "提示词 & 技能", element: placeholder },
  { path: "/settings", nav: "settings", title: "设置", element: placeholder },
];

const rootEl = document.getElementById("root");
if (rootEl) {
  ReactDOM.createRoot(rootEl).render(<AppShell routes={defaultRoutes} />);
}
