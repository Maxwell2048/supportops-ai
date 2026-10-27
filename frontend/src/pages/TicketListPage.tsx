import { useState } from "react";
import type { FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { invalidateTickets, listOptions, queryView } from "../state/queries.ts";
import {
  emptyFilters,
  filterKey,
  normalizeFilters,
} from "../state/ticketState.ts";
import type { TicketFilters } from "../state/ticketState.ts";
import type { Session } from "../App.tsx";
import { Empty, ErrorPanel, Loading } from "../components/Feedback.tsx";
import {
  PriorityLabel,
  shortId,
  Status,
  Time,
} from "../components/TicketMeta.tsx";

function FilterForm({
  filters,
  apply,
}: {
  filters: TicketFilters;
  apply: (value: TicketFilters) => void;
}) {
  const [draft, setDraft] = useState(filters);
  function submit(event: FormEvent) {
    event.preventDefault();
    apply(normalizeFilters(draft));
  }
  return (
    <form className="filter-bar" onSubmit={submit} aria-label="Ticket filters">
      <div className="search-field">
        <label htmlFor="ticket-search">Search requests</label>
        <input
          id="ticket-search"
          type="search"
          maxLength={200}
          value={draft.q}
          placeholder="Search title or original request"
          onChange={(event) => setDraft({ ...draft, q: event.target.value })}
        />
      </div>
      <div>
        <label htmlFor="status-filter">Status</label>
        <select
          id="status-filter"
          value={draft.status}
          onChange={(event) =>
            setDraft({
              ...draft,
              status: event.target.value as TicketFilters["status"],
            })
          }
        >
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="in_progress">In progress</option>
          <option value="waiting_customer">Waiting for customer</option>
          <option value="resolved">Resolved</option>
          <option value="closed">Closed</option>
        </select>
      </div>
      <div>
        <label htmlFor="priority-filter">Priority</label>
        <select
          id="priority-filter"
          value={draft.priority}
          onChange={(event) =>
            setDraft({
              ...draft,
              priority: event.target.value as TicketFilters["priority"],
            })
          }
        >
          <option value="">All priorities</option>
          <option value="low">Low</option>
          <option value="normal">Normal</option>
          <option value="high">High</option>
          <option value="urgent">Urgent</option>
        </select>
      </div>
      <button className="button primary" type="submit">
        Apply filters
      </button>
      <button
        className="button secondary"
        type="button"
        onClick={() => {
          setDraft(emptyFilters);
          apply(emptyFilters);
        }}
      >
        Clear filters
      </button>
    </form>
  );
}

export function TicketListPage({
  session,
  filters,
  cursors: pages,
  onPage,
  onFilters,
}: {
  session: Session;
  filters: TicketFilters;
  cursors: (string | null)[];
  onPage: (value: (string | null)[]) => void;
  onFilters: (value: TicketFilters) => void;
}) {
  const cursor = pages[pages.length - 1];
  const client = useQueryClient();
  const query = useQuery(listOptions(session, filters, cursor));
  const state = queryView(query);
  const reload = () => {
    void invalidateTickets(client, session);
  };
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
      <FilterForm
        key={filterKey(filters)}
        filters={filters}
        apply={onFilters}
      />
      {session.user.role === "requester" && (
        <p>
          <a className="button primary" href="#/tickets/new">
            New request
          </a>
        </p>
      )}
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
          <>
            <ErrorPanel error={state.error} retry={reload} />
            {state.error.code === "invalid_cursor" && (
              <button
                className="button secondary"
                onClick={() => onPage([null])}
              >
                Start from first page
              </button>
            )}
          </>
        ) : state.data.items.length === 0 ? (
          <Empty title="Nothing here yet">
            {pages.length === 1
              ? filters.q || filters.status || filters.priority
                ? "No tickets match these filters. Try another search or clear the filters."
                : "There are no tickets available to your account right now."
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
              onClick={() => onPage(pages.slice(0, -1))}
            >
              Previous
            </button>
            <button
              className="button compact secondary"
              disabled={state.status !== "success" || !state.data.next_cursor}
              onClick={() => {
                if (state.status === "success" && state.data.next_cursor)
                  onPage([...pages, state.data.next_cursor]);
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
