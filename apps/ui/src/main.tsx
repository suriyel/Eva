/**
 * Vite entry — mount AppShell into #root. Routes are a minimal placeholder set
 * for F12; F21/F22 will register real page components.
 */
import * as React from "react";
import ReactDOM from "react-dom/client";
import { AppShell, type RouteSpec } from "./app/app-shell";
import "./theme/tokens.css";

// F12 预留全部 8 个导航占位路由；F21 / F22 feature 会逐项替换 element 为真实页面。
// 保留占位路由的理由：Sidebar 的 8 项（UCD §3.8）全部可点击，避免"display-only"缺陷；
// 占位 element 为一个主内容容器 div，满足 AppShell children slot 契约，无业务逻辑。
const placeholder = (
  <div data-component="route-placeholder" style={{ padding: 24, color: "var(--fg-dim)" }} />
);
const defaultRoutes: RouteSpec[] = [
  { path: "/", nav: "overview", title: "总览", element: placeholder },
  { path: "/hil", nav: "hil", title: "HIL 待答", element: placeholder },
  { path: "/stream", nav: "stream", title: "Ticket 流", element: placeholder },
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
