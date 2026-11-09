import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { Session } from "../App.tsx";
import { api, ApiError } from "../api/client.ts";
import { WriteAttempt } from "../state/writes.ts";
import { invalidateTickets } from "../state/queries.ts";
import { ErrorPanel } from "../components/Feedback.tsx";

export function CreateTicketPage({
  session,
  backHref,
}: {
  session: Session;
  backHref: string;
}) {
  const [title, setTitle] = useState(""),
    [body, setBody] = useState(""),
    [phone, setPhone] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const attempt = useRef(new WriteAttempt()),
    busy = useRef(false),
    controller = useRef<AbortController | null>(null);
  const client = useQueryClient();
  useEffect(() => () => controller.current?.abort(), []);
  const mutation = useMutation({
    retry: false,
    mutationFn: async () => {
      const payload = { title: title.trim(), body: body.trim(), ...(phone.trim() ? { contact_phone: phone.trim() } : {}) };
      if (
        !payload.title ||
        !payload.body ||
        payload.title.includes("\0") ||
        payload.body.includes("\0")
      )
        throw new ApiError(
          422,
          "invalid_input",
          "Enter a title and description without null characters.",
        );
      controller.current = new AbortController();
      return api.createTicket(
        session.token,
        payload,
        attempt.current.key("create", payload),
        controller.current.signal,
      );
    },
  });
  if (session.user.role !== "requester")
    return <p>Only requesters can submit new tickets.</p>;
  return (
    <>
      <a className="back-link" href={backHref}>
        ← Back to tickets
      </a>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Tell us what happened</p>
          <h1>New support request</h1>
          <p>Your signed-in email is used as the contact address.</p>
        </div>
      </header>
      <section className="panel write-panel">
        {error && <ErrorPanel error={error} />}
        {uncertain && (
          <p role="alert">
            The result is uncertain. Retry the same request to recover its
            result without creating a duplicate.
          </p>
        )}
        <form
          aria-label="New support request"
          onSubmit={async (event) => {
            event.preventDefault();
            if (busy.current) return;
            busy.current = true;
            setError(null);
            try {
              const ticket = await mutation.mutateAsync();
              if (controller.current?.signal.aborted) return;
              attempt.current.clear();
              setUncertain(false);
              await invalidateTickets(client, session);
              if (!controller.current?.signal.aborted)
                window.location.hash = `/tickets/${ticket.id}`;
            } catch (failure) {
              if (controller.current?.signal.aborted) return;
              const safe =
                failure instanceof ApiError
                  ? failure
                  : new ApiError(
                      0,
                      "unexpected_error",
                      "Unable to submit your request.",
                    );
              setError(safe);
              setUncertain(
                safe.status === 0 ||
                  safe.status >= 500 ||
                  safe.code === "invalid_response",
              );
            } finally {
              busy.current = false;
            }
          }}
        >
          <fieldset disabled={mutation.isPending || uncertain}>
            <legend className="sr-only">Request details</legend>
            <label htmlFor="create-title">Title</label>
            <input
              id="create-title"
              required
              maxLength={200}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              autoFocus
            />
            <label htmlFor="create-body">What do you need help with?</label>
            <textarea
              id="create-body"
              rows={8}
              required
              maxLength={10000}
              value={body}
              onChange={(event) => setBody(event.target.value)}
              aria-describedby="create-help"
            />
            <p id="create-help" className="small">
              Maximum 10,000 characters. Use synthetic information in this
              demonstration.
            </p>
            <label htmlFor="create-phone">Contact phone (optional)</label>
            <input id="create-phone" type="tel" maxLength={40} value={phone}
              onChange={(event) => setPhone(event.target.value)} autoComplete="tel" />
          </fieldset>
          <button
            className="button primary"
            disabled={mutation.isPending}
            type="submit"
          >
            {mutation.isPending
              ? "Submitting…"
              : uncertain
                ? "Retry same request"
                : "Submit request"}
          </button>
          <p className="small muted">
            Drafts stay in memory on this page. Leaving, reloading or signing
            out discards them.
          </p>
        </form>
      </section>
    </>
  );
}
