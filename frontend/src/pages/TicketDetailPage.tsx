import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  detailOptions,
  invalidateTickets,
  queryView,
} from "../state/queries.ts";
import type { Session } from "../App.tsx";
import { Empty, ErrorPanel, Loading } from "../components/Feedback.tsx";
import {
  PriorityLabel,
  shortId,
  Status,
  Time,
} from "../components/TicketMeta.tsx";

export function TicketDetailPage({
  id,
  session,
  backHref,
}: {
  id: string;
  session: Session;
  backHref: string;
}) {
  const client = useQueryClient();
  const query = useQuery(detailOptions(session, id));
  const state = queryView(query);
  const reload = () => {
    void invalidateTickets(client, session);
  };
  if (state.status === "loading") return <Loading label="Loading ticket" />;
  if (state.status === "error")
    return <ErrorPanel error={state.error} retry={reload} />;
  const ticket = state.data;
  return (
    <>
      <a className="back-link" href={backHref}>
        ← Back to tickets
      </a>
      <header className="page-heading detail-heading">
        <div>
          <p className="eyebrow">Request #{shortId(ticket.id)}</p>
          <h1>{ticket.title}</h1>
          <div className="actions">
            <Status status={ticket.status} />
            {ticket.archived && (
              <span className="archived-label">Archived</span>
            )}
          </div>
        </div>
        <button className="button secondary" onClick={reload}>
          Refresh ticket
        </button>
      </header>
      <div className="detail-grid">
        <div className="detail-content">
          <section
            className="panel description"
            aria-labelledby="description-heading"
          >
            <div className="panel-heading">
              <h2 id="description-heading">Original request</h2>
            </div>
            <div className="panel-body">
              <p className="text-content">{ticket.body}</p>
              <p className="small muted">
                Submitted <Time value={ticket.created_at} />
              </p>
            </div>
          </section>
          <section className="panel" aria-labelledby="conversation-heading">
            <div className="panel-heading">
              <h2 id="conversation-heading">Conversation</h2>
              <span className="small muted">
                {ticket.messages.length}{" "}
                {ticket.messages.length === 1 ? "message" : "messages"}
              </span>
            </div>
            {ticket.messages.length === 0 ? (
              <Empty title="The conversation starts here">
                There are no replies to this request yet.
              </Empty>
            ) : (
              <ol className="message-list">
                {ticket.messages.map((message) => (
                  <li
                    className={`message message-${message.visibility}`}
                    key={message.id}
                  >
                    <div className="message-heading">
                      <span className="avatar" aria-hidden="true">
                        {message.author_id === session.user.id ? "Y" : "S"}
                      </span>
                      <div>
                        <strong>
                          {message.author_id === session.user.id
                            ? "You"
                            : session.user.role === "requester"
                              ? "Support team"
                              : `Participant ${shortId(message.author_id)}`}
                        </strong>
                        <span
                          className={`visibility visibility-${message.visibility}`}
                        >
                          {message.visibility === "internal"
                            ? "Internal note · staff only"
                            : "Public reply"}
                        </span>
                      </div>
                      <span className="small muted">
                        <Time value={message.created_at} />
                      </span>
                    </div>
                    <p className="text-content">{message.body}</p>
                  </li>
                ))}
              </ol>
            )}
          </section>
          {session.user.role !== "requester" && ticket.events && (
            <section className="panel" aria-labelledby="history-heading">
              <div className="panel-heading">
                <h2 id="history-heading">Activity</h2>
                <span className="small muted">Staff view</span>
              </div>
              {ticket.events.length === 0 ? (
                <Empty title="No activity recorded">
                  Recorded updates will appear here.
                </Empty>
              ) : (
                <ol className="event-list">
                  {ticket.events.map((event) => (
                    <li key={event.id}>
                      <div>
                        <strong>{event.event_type.replaceAll("_", " ")}</strong>
                        <span className="small muted">
                          {" "}
                          · Version {event.ticket_version} ·{" "}
                          {shortId(event.actor_id)}
                        </span>
                      </div>
                      <span className="small muted">
                        <Time value={event.created_at} />
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          )}
        </div>
        <aside
          className="panel properties"
          aria-labelledby="properties-heading"
        >
          <div className="panel-heading">
            <h2 id="properties-heading">Ticket details</h2>
          </div>
          <dl>
            <div>
              <dt>Priority</dt>
              <dd>
                <PriorityLabel priority={ticket.priority} />
              </dd>
            </div>
            <div>
              <dt>Assigned to</dt>
              <dd>
                {session.user.role === "requester" ? (
                  ticket.assignee_id ? (
                    "Support team"
                  ) : (
                    "Awaiting assignment"
                  )
                ) : ticket.assignee_id ? (
                  <code title={ticket.assignee_id}>
                    {shortId(ticket.assignee_id)}
                  </code>
                ) : (
                  "Not assigned"
                )}
              </dd>
            </div>
            <div>
              <dt>Last updated</dt>
              <dd>
                <Time value={ticket.updated_at} />
              </dd>
            </div>
            <div>
              <dt>Time zone</dt>
              <dd>Perth (UTC+8)</dd>
            </div>
            <div>
              <dt>Ticket ID</dt>
              <dd className="full-id">
                <code>{ticket.id}</code>
              </dd>
            </div>
          </dl>
        </aside>
      </div>
    </>
  );
}
