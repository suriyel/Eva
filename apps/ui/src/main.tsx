/**
 * Vite entry — mount AppShell into #root. Routes are a minimal placeholder set
 * for F12; F21/F22 will register real page components.
 */
import * as React from "react";
import ReactDOM from "react-dom/client";
import { AppShell, type RouteSpec } from "./app/app-shell";
import "./theme/tokens.css";

const defaultRoutes: RouteSpec[] = [
  { path: "/", nav: "overview", title: "总览", element: <div /> },
  { path: "/hil", nav: "hil", title: "HIL 待答", element: <div /> },
];

const rootEl = document.getElementById("root");
if (rootEl) {
  ReactDOM.createRoot(rootEl).render(<AppShell routes={defaultRoutes} />);
}
