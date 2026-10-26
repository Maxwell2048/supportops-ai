import { useCallback, useEffect, useState } from "react";
import type { User } from "./api/contracts.ts";
import { isUuid } from "./api/contracts.ts";
import { ApiError } from "./api/client.ts";
import { ErrorPanel } from "./components/Feedback.tsx";
import { LoginPage } from "./pages/LoginPage.tsx";
import { TicketListPage } from "./pages/TicketListPage.tsx";
import { TicketDetailPage } from "./pages/TicketDetailPage.tsx";

export interface Session {
  key: string;
  token: string;
  user: User;
  expiresAt: number;
}
function routeFromHash() {
  const path = window.location.hash.slice(1) || "/tickets";
  if (path === "/tickets" || path === "/") return { kind: "list" as const };
  const match = /^\/tickets\/([^/]+)$/.exec(path);
  if (match && isUuid(match[1]))
    return { kind: "detail" as const, id: match[1] };
  return { kind: "missing" as const };
}
function Workspace({
  session,
  onSignOut,
  onExpired,
}: {
  session: Session;
  onSignOut: () => void;
  onExpired: () => void;
}) {
  const [route, setRoute] = useState(routeFromHash);
  const routeKey = route.kind === "detail" ? route.id : route.kind;
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [routeKey]);
  useEffect(() => {
    const change = () => setRoute(routeFromHash());
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  return (
    <div className="workspace">
      <a
        className="skip-link"
        href="#workspace-main"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("workspace-main")?.focus();
        }}
      >
        Skip to content
      </a>
      <aside className="sidebar">
        <a className="brand" href="#/tickets">
          <span className="brand-mark" aria-hidden="true">
            S
          </span>
          SupportOps<span className="brand-ai">AI</span>
        </a>
        <p className="nav-heading">Workspace</p>
        <nav aria-label="Main navigation">
          <a
            className="nav-link active"
            href="#/tickets"
            aria-current={route.kind === "list" ? "page" : undefined}
          >
            <span aria-hidden="true">▤</span>Tickets
            <span className="nav-arrow" aria-hidden="true">
              ↗
            </span>
          </a>
        </nav>
        <div className="sidebar-note">
          <span className="live-dot" aria-hidden="true" />
          <span>
            Synthetic workspace
            <br />
            <span className="muted">Human-led support.</span>
          </span>
        </div>
        <div className="account">
          <span className="avatar" aria-hidden="true">
            {session.user.email[0]?.toUpperCase()}
          </span>
          <div>
            <strong>
              {session.user.role[0].toUpperCase() + session.user.role.slice(1)}
            </strong>
            <span className="account-email">{session.user.email}</span>
          </div>
        </div>
        <button className="sign-out" onClick={onSignOut}>
          Sign out <span aria-hidden="true">↗</span>
        </button>
      </aside>
      <div className="workspace-main">
        <header className="topbar">
          <span>
            Workspace <span className="breadcrumb-separator">/</span>{" "}
            <strong>Tickets</strong>
          </span>
          <span className="workspace-tag">Support operations</span>
        </header>
        <main id="workspace-main" tabIndex={-1} className="page-content">
          {route.kind === "list" ? (
            <TicketListPage session={session} onExpired={onExpired} />
          ) : route.kind === "detail" ? (
            <TicketDetailPage
              key={route.id}
              id={route.id}
              session={session}
              onExpired={onExpired}
            />
          ) : (
            <ErrorPanel
              error={
                new ApiError(
                  404,
                  "not_found",
                  "This page address is not available. Return to your tickets.",
                )
              }
            />
          )}
        </main>
        <footer className="workspace-footer">
          <span>SupportOps AI</span>
          <span>Built around people. Backed by a clear history.</span>
        </footer>
      </div>
    </div>
  );
}
export function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [notice, setNotice] = useState("");
  const expired = useCallback(() => {
    setSession(null);
    setNotice("Your session has expired. Please sign in again.");
  }, []);
  useEffect(() => {
    if (!session) return;
    const timer = window.setTimeout(
      expired,
      Math.max(0, session.expiresAt - Date.now()),
    );
    return () => window.clearTimeout(timer);
  }, [session, expired]);
  function signIn(value: Session) {
    if (value.expiresAt <= Date.now()) {
      expired();
      return;
    }
    setNotice("");
    setSession(value);
  }
  function signOut() {
    setSession(null);
    setNotice("You have signed out.");
    window.location.hash = "/tickets";
  }
  // Unmount all private state between sessions, including same-user sign-ins.
  return session ? (
    <Workspace
      key={session.key}
      session={session}
      onSignOut={signOut}
      onExpired={expired}
    />
  ) : (
    <LoginPage notice={notice} onSignIn={signIn} />
  );
}
