import { useCallback, useState } from "react";
import { api } from "../api/client.ts";
import type { Session } from "../App.tsx";
import { Empty, ErrorPanel, Loading } from "../components/Feedback.tsx";
import {
  PriorityLabel,
  shortId,
  Status,
  Time,
} from "../components/TicketMeta.tsx";
import { useRemote } from "../hooks/useRemote.ts";

export function TicketListPage({
  session,
  onExpired,
}: {
  session: Session;
  onExpired: () => void;
}) {
  const [pages, setPages] = useState<(string | null)[]>([null]);
  const cursor = pages[pages.length - 1];
  const load = useCallback(
    (signal: AbortSignal) => api.tickets(session.token, cursor, signal),
    [session.token, cursor],
  );
  const { state, reload } = useRemote(cursor ?? "first-page", load, onExpired);
  const scope =
    session.user.role === "requester"
      ? "Your submitted requests and their latest progress."
      : session.user.role === "agent"
        ? "The requests currently assigned to you."
        : "A shared view of every support request.";
  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Your workspace, at a glance</p>
          <h1>Tickets</h1>
          <p className="muted">{scope}</p>
        </div>
        <button
          className="button secondary"
          onClick={reload}
          disabled={state.status === "loading"}
        >
          Refresh tickets
        </button>
      </header>
      <section className="panel" aria-labelledby="list-heading">
        <div className="panel-heading">
          <h2 id="list-heading">
            {session.user.role === "agent"
              ? "Assigned to you"
              : session.user.role === "requester"
                ? "Your requests"
                : "All requests"}
          </h2>
          <span className="muted small">Updated times · Perth (UTC+8)</span>
        </div>
        {state.status === "loading" ? (
          <Loading label="Loading tickets" />
        ) : state.status === "error" ? (
          <ErrorPanel error={state.error} retry={reload} />
        ) : state.data.items.length === 0 ? (
          <Empty title="Nothing here yet">
            {pages.length === 1
              ? "There are no tickets available to your account right now."
              : "There are no more tickets on this page."}
          </Empty>
        ) : (
          <div className="table-scroll">
            <table>
              <caption className="sr-only">
                Tickets available to your current account
              </caption>
              <thead>
                <tr>
                  <th scope="col">Request</th>
                  <th scope="col">Status</th>
                  <th scope="col">Priority</th>
                  <th scope="col">Updated</th>
                </tr>
              </thead>
              <tbody>
                {state.data.items.map((ticket) => (
                  <tr key={ticket.id}>
                    <td>
                      <a
                        className="ticket-link"
                        href={`#/tickets/${ticket.id}`}
                      >
                        <span className="ticket-ref">
                          #{shortId(ticket.id)}
                        </span>
                        <span>{ticket.title}</span>
                      </a>
                      {ticket.archived && (
                        <span className="archived-label">Archived</span>
                      )}
                    </td>
                    <td>
                      <Status status={ticket.status} />
                    </td>
                    <td>
                      <PriorityLabel priority={ticket.priority} />
                    </td>
                    <td className="date-cell">
                      <Time value={ticket.updated_at} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="pagination">
          <span className="muted small">
            Page {pages.length}
            {state.status === "success"
              ? ` · ${state.data.items.length} ${state.data.items.length === 1 ? "ticket" : "tickets"}`
              : ""}
          </span>
          <div className="actions">
            <button
              className="button compact secondary"
              disabled={pages.length === 1 || state.status === "loading"}
              onClick={() => setPages((value) => value.slice(0, -1))}
            >
              Previous
            </button>
            <button
              className="button compact secondary"
              disabled={state.status !== "success" || !state.data.next_cursor}
              onClick={() => {
                if (state.status === "success" && state.data.next_cursor)
                  setPages((value) => [...value, state.data.next_cursor]);
              }}
            >
              Next
            </button>
          </div>
        </div>
      </section>
      <p className="page-note">
        Only tickets available to your current account appear here.
      </p>
    </>
  );
}
