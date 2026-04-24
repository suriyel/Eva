/**
 * AppShell — top-level application shell.
 * §4 IC: <QueryClientProvider> + <BrowserRouter> + <PageFrame> + <ErrorBoundary>.
 * WS client singleton connects on mount / disconnects on unmount.
 */
import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, useLocation, useNavigate } from "react-router-dom";
import { PageFrame } from "../components/page-frame";
import type { NavId } from "../components/sidebar";
import { HarnessWsClient } from "../ws/client";
import { getTokensCssText } from "../theme/tokens-inline";

export interface RouteSpec {
  path: string;
  nav: NavId;
  title: string;
  element: React.ReactNode;
}

export interface AppShellProps {
  routes: RouteSpec[];
}

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error): { error: Error } {
    return { error };
  }
  render(): React.ReactNode {
    if (this.state.error) {
      return (
        <div data-component="error-boundary" style={{ padding: 16, color: "var(--state-fail)" }}>
          {this.state.error.message}
        </div>
      );
    }
    return this.props.children;
  }
}

function resolveWsBase(): string {
  const injected = (globalThis as unknown as { __HARNESS_WS_BASE__?: string }).__HARNESS_WS_BASE__;
  if (typeof injected === "string" && injected.length > 0) return injected;
  if (typeof window !== "undefined") {
    const host = window.location.hostname || "127.0.0.1";
    const port = window.location.port || "8765";
    return `ws://${host}:${port}`;
  }
  return "ws://127.0.0.1:8765";
}

function TokensStyleTag(): React.ReactElement | null {
  // Inject tokens.css text at runtime so happy-dom / jsdom tests and production builds
  // share the same `:root { --bg-app … }` declarations. In production Vite will also
  // import the CSS bundle via main.tsx, this is purely defensive.
  const css = getTokensCssText();
  return <style data-component="tokens">{css}</style>;
}

function Frame({ routes }: { routes: RouteSpec[] }): React.ReactElement {
  const location = useLocation();
  const navigate = useNavigate();
  const current = routes.find((r) => r.path === location.pathname) ?? routes[0];
  const active: NavId = current?.nav ?? ("overview" as NavId);
  const title = current?.title ?? "Harness";
  const onNavigate = (id: NavId): void => {
    const target = routes.find((r) => r.nav === id);
    if (target) navigate(target.path);
  };
  return (
    <PageFrame active={active} title={title} onNavigate={onNavigate}>
      <Routes>
        {routes.map((r) => (
          <Route key={r.path} path={r.path} element={r.element} />
        ))}
      </Routes>
    </PageFrame>
  );
}

function EmptyFrame(): React.ReactElement {
  return (
    <PageFrame active={"overview" as NavId} title="Harness">
      <div />
    </PageFrame>
  );
}

export function AppShell({ routes }: AppShellProps): React.ReactElement {
  const [queryClient] = React.useState(
    () => new QueryClient({ defaultOptions: { queries: { retry: false } } }),
  );

  React.useEffect(() => {
    const client = HarnessWsClient.singleton();
    try {
      client.connect(resolveWsBase());
    } catch {
      /* invalid URL → stay disconnected */
    }
    return () => {
      client.disconnect();
    };
  }, []);

  const hasRoutes = Array.isArray(routes) && routes.length > 0;

  return (
    <div data-component="app-shell" style={{ width: "100vw", height: "100vh", background: "var(--bg-app)" }}>
      <TokensStyleTag />
      <ErrorBoundary>
        <QueryClientProvider client={queryClient}>
          {hasRoutes ? (
            <BrowserRouter>
              <Frame routes={routes} />
            </BrowserRouter>
          ) : (
            <EmptyFrame />
          )}
        </QueryClientProvider>
      </ErrorBoundary>
    </div>
  );
}
