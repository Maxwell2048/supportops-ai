import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Session } from "../App.tsx";
import type { TicketSummary } from "../api/contracts.ts";
import { api } from "../api/client.ts";
import { needsText, operations } from "../state/writes.ts";
import type { Operation } from "../state/writes.ts";
import type { TicketWrite } from "../hooks/useTicketWrite.ts";
import { ErrorPanel } from "./Feedback.tsx";

const labels: Record<Operation, string> = {
  public: "Send public reply",
  internal: "Add internal note",
  start: "Start or resume work",
  wait: "Wait for customer",
  resolve: "Resolve ticket",
  reopen: "Reopen ticket",
  close: "Close ticket",
  assign: "Change assignment",
  priority: "Change priority",
  archive: "Archive ticket",
  unarchive: "Unarchive ticket",
};

function AgentSelect({
  session,
  value,
  onChange,
  onReady,
}: {
  session: Session;
  value: string;
  onChange: (value: string) => void;
  onReady: (ready: boolean) => void;
}) {
  const query = useQuery({
    queryKey: ["session", session.key, "agents"],
    queryFn: ({ signal }) => api.agents(session.token, signal),
  });
  const ready = !query.isFetching && !query.isError && !!query.data;
  const selectionAvailable =
    !value || !!query.data?.some((agent) => agent.id === value);
  useEffect(() => {
    onReady(ready && selectionAvailable);
    return () => onReady(false);
  }, [ready, selectionAvailable, onReady]);
  return (
    <>
      <label htmlFor="write-agent">Available agent</label>
      <select
        id="write-agent"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={!ready}
      >
        <option value="">Unassigned</option>
        {ready && !selectionAvailable && (
          <option value={value} disabled>
            Selected agent unavailable — choose another
          </option>
        )}
        {ready &&
          query.data!.map((agent) => (
            <option key={agent.id} value={agent.id}>
              {agent.email}
            </option>
          ))}
      </select>
      {!ready && (
        <p role="status">
          {query.isError
            ? "Unable to load available agents."
            : "Checking available agents…"}
        </p>
      )}
      <button
        type="button"
        className="button secondary"
        onClick={() => void query.refetch()}
      >
        Refresh agents
      </button>
      <p className="small">
        Assignment is checked again when saved. An unavailable agent cannot be
        assigned.
      </p>
    </>
  );
}
export function TicketActions({
  ticket,
  session,
  write,
}: {
  ticket: TicketSummary;
  session: Session;
  write: TicketWrite;
}) {
  const [directoryReady, setDirectoryReady] = useState(false);
  const available = operations(ticket, session.user.role);
  const operation = write.draft.operation;
  const selected = available.includes(operation);
  return (
    <section className="panel write-panel" aria-labelledby="write-heading">
      <h2 id="write-heading">Update this ticket</h2>
      {write.notice && <p role="status">{write.notice}</p>}
      {write.error && <ErrorPanel error={write.error} />}
      {write.error?.status === 409 && (
        <>
          <p>
            Your input is retained. Review the current status, conversation and
            version {ticket.version} above before continuing.
          </p>
          <button
            className="button secondary"
            type="button"
            onClick={() => write.review(ticket)}
          >
            Use reviewed version {ticket.version}
          </button>
        </>
      )}
      {write.uncertain && (
        <p role="alert">
          The result is uncertain. Retry the same request to check its result
          safely. Editing is locked until this is resolved.
        </p>
      )}
      <form
        aria-label="Ticket update"
        onSubmit={(event) => {
          event.preventDefault();
          void write.submit(ticket);
        }}
      >
        <fieldset
          disabled={
            write.pending || write.uncertain || write.error?.status === 409
          }
        >
          <legend className="sr-only">Ticket action and content</legend>
          <label htmlFor="write-action">Action</label>
          <select
            id="write-action"
            disabled={available.length === 0}
            value={selected ? operation : ""}
            onChange={(event) =>
              write.edit(ticket, { operation: event.target.value as Operation })
            }
            required
          >
            {!selected && <option value="">Choose an available action</option>}
            {available.map((action) => (
              <option key={action} value={action}>
                {labels[action]}
              </option>
            ))}
          </select>
          {needsText(operation) && (selected || !!write.draft.text) && (
            <>
              <label htmlFor="write-body">
                {operation === "internal"
                  ? "Internal note (staff only)"
                  : operation === "reopen"
                    ? "Reopening reason (public)"
                    : "Public reply"}
              </label>
              <textarea
                id="write-body"
                required={selected}
                readOnly={!selected}
                maxLength={operation === "reopen" ? 2000 : 10000}
                rows={5}
                value={write.draft.text}
                onChange={(event) =>
                  write.edit(ticket, { text: event.target.value })
                }
                aria-describedby="write-help"
              />
              <p id="write-help" className="small">
                {operation === "internal"
                  ? "Only authorized staff can read this note."
                  : "The requester can read this text."}{" "}
                Maximum {operation === "reopen" ? "2,000" : "10,000"}{" "}
                characters.
              </p>
            </>
          )}
          {operation === "assign" && (
            <AgentSelect
              session={session}
              value={write.draft.assignee}
              onChange={(assignee) => write.edit(ticket, { assignee })}
              onReady={setDirectoryReady}
            />
          )}
          {operation === "priority" && (
            <>
              <label htmlFor="write-priority">New priority</label>
              <select
                id="write-priority"
                value={write.draft.priority}
                onChange={(event) =>
                  write.edit(ticket, { priority: event.target.value })
                }
              >
                {["low", "normal", "high", "urgent"].map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </>
          )}
        </fieldset>
        <p className="small">
          Current version: {ticket.version}. Draft version:{" "}
          {write.version ?? ticket.version}.{" "}
          {available.length
            ? "Changes are saved only after you submit."
            : "No actions are available for this ticket."}
        </p>
        <button
          className="button primary"
          type="submit"
          disabled={
            write.pending ||
            (!write.uncertain &&
              (!selected || (operation === "assign" && !directoryReady))) ||
            write.error?.status === 409
          }
        >
          {write.pending
            ? "Saving…"
            : write.uncertain
              ? "Retry same request"
              : selected
                ? labels[operation]
                : "Choose an action"}
        </button>
      </form>
      <p className="small muted">
        Drafts stay in memory on this page. Leaving the page, reloading or
        signing out discards them.
      </p>
    </section>
  );
}
