import { useCallback, useEffect, useRef, useState } from "react";
import type { User } from "./api/contracts.ts";
import { QueryClientProvider } from "@tanstack/react-query";
import type { QueryClient } from "@tanstack/react-query";
import { createSessionClient } from "./state/queries.ts";
import {
  emptyFilters,
  filterKey,
  listHref,
  routeFromHash,
} from "./state/ticketState.ts";
import { ErrorPanel } from "./components/Feedback.tsx";
import { LoginPage } from "./pages/LoginPage.tsx";
import { TicketListPage } from "./pages/TicketListPage.tsx";
import { TicketDetailPage } from "./pages/TicketDetailPage.tsx";
import { CreateTicketPage } from "./pages/CreateTicketPage.tsx";

export interface Session {
  key: string;
  token: string;
  user: User;
  expiresAt: number;
}
function Workspace({
  session,
  onSignOut,
}: {
  session: Session;
  onSignOut: () => void;
}) {
  const [route, setRoute] = useState(() => routeFromHash(window.location.hash));
  const lastList = useRef(listHref(emptyFilters));
  const [paging, setPaging] = useState({
    scope: filterKey(emptyFilters),
    cursors: [null] as (string | null)[],
  });
  const backHref =
    route.kind === "list" ? listHref(route.filters) : lastList.current;
  const scope = route.kind === "list" ? filterKey(route.filters) : paging.scope;
  const cursors = paging.scope === scope ? paging.cursors : [null];
  useEffect(() => {
    if (route.kind === "list") {
      lastList.current = listHref(route.filters);
      setPaging((value) =>
        value.scope === scope ? value : { scope, cursors: [null] },
      );
    }
  }, [route, scope]);
  const routeKey = route.kind === "detail" ? route.id : route.kind;
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [routeKey]);
  useEffect(() => {
    const change = () => setRoute(routeFromHash(window.location.hash));
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
        <a className="brand" href={backHref}>
          <span className="brand-mark" aria-hidden="true">
            S
          </span>
          SupportOps<span className="brand-ai">AI</span>
        </a>
        <p className="nav-heading">Workspace</p>
        <nav aria-label="Main navigation">
          <a
            className="nav-link active"
            href={backHref}
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
            <TicketListPage
              key={JSON.stringify([
                filterKey(route.filters),
                cursors[cursors.length - 1],
              ])}
              session={session}
              filters={route.filters}
              cursors={cursors}
              onPage={(next) => setPaging({ scope, cursors: next })}
              onFilters={(filters) => {
                setPaging({ scope: filterKey(filters), cursors: [null] });
                window.location.hash = listHref(filters).slice(1);
              }}
            />
          ) : route.kind === "create" ? (
            <CreateTicketPage session={session} backHref={backHref} />
          ) : route.kind === "detail" ? (
            <TicketDetailPage
              key={route.id}
              id={route.id}
              session={session}
              backHref={backHref}
            />
          ) : (
            <ErrorPanel error={route.error} />
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
  const cache = useRef<QueryClient | null>(null);
  useEffect(
    () => () => {
      cache.current?.clear();
    },
    [],
  );
  const expired = useCallback(() => {
    cache.current?.clear();
    cache.current = null;
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
    cache.current?.clear();
    cache.current = createSessionClient(expired);
    setNotice("");
    setSession(value);
  }
  function signOut() {
    cache.current?.clear();
    cache.current = null;
    setSession(null);
    setNotice("You have signed out.");
    window.location.hash = "/tickets";
  }
  // Unmount all private state between sessions, including same-user sign-ins.
  return session ? (
    <QueryClientProvider client={cache.current!}>
      <Workspace key={session.key} session={session} onSignOut={signOut} />
    </QueryClientProvider>
  ) : (
    <LoginPage notice={notice} onSignIn={signIn} />
  );
}
