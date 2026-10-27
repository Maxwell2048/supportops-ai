import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { Session } from "../App.tsx";
import type { TicketSummary } from "../api/contracts.ts";
import { api, ApiError } from "../api/client.ts";
import { buildWrite, emptyDraft, WriteAttempt } from "../state/writes.ts";
import type { Draft } from "../state/writes.ts";
import { invalidateTickets } from "../state/queries.ts";

export function useTicketWrite(session: Session) {
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [version, setVersion] = useState<number | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState("");
  const [uncertain, setUncertain] = useState(false);
  const attempt = useRef(new WriteAttempt());
  const submitted = useRef<ReturnType<typeof buildWrite> | null>(null);
  const busy = useRef(false),
    controller = useRef<AbortController | null>(null);
  const client = useQueryClient();
  useEffect(
    () => () => {
      controller.current?.abort();
    },
    [],
  );
  const mutation = useMutation({
    retry: false,
    mutationFn: async (ticket: TicketSummary) => {
      let write: ReturnType<typeof buildWrite>;
      try {
        write =
          uncertain && submitted.current
            ? submitted.current
            : buildWrite(
                ticket,
                session.user.role,
                draft,
                version ?? ticket.version,
              );
      } catch {
        throw new ApiError(
          422,
          "invalid_input",
          "Check the selected action and enter valid text within the displayed limit.",
        );
      }
      submitted.current = write;
      const key = attempt.current.key(`${ticket.id}:${write.kind}`, write.body);
      controller.current = new AbortController();
      return write.kind === "message"
        ? api.message(
            ticket.id,
            session.token,
            write.body,
            key,
            controller.current.signal,
          )
        : api.patchTicket(
            ticket.id,
            session.token,
            write.body,
            key,
            controller.current.signal,
          );
    },
  });
  return {
    draft,
    version,
    error,
    notice,
    uncertain,
    pending: mutation.isPending,
    edit(ticket: TicketSummary, next: Partial<Draft>) {
      setVersion((value) => value ?? ticket.version);
      setDraft((value) => ({ ...value, ...next }));
      setNotice("");
    },
    review(ticket: TicketSummary) {
      setVersion(ticket.version);
      attempt.current.clear();
      setError(null);
      setUncertain(false);
      setNotice(
        `Draft retained. You reviewed version ${ticket.version}; submit when ready.`,
      );
    },
    async submit(ticket: TicketSummary) {
      if (busy.current || error?.status === 409) return;
      busy.current = true;
      setVersion((value) => value ?? ticket.version);
      setError(null);
      setNotice("");
      try {
        await mutation.mutateAsync(ticket);
        if (controller.current?.signal.aborted) return;
        attempt.current.clear();
        setDraft(emptyDraft);
        setVersion(null);
        setUncertain(false);
        setNotice("Your update was saved.");
        await invalidateTickets(client, session);
      } catch (failure) {
        if (controller.current?.signal.aborted) return;
        const safe =
          failure instanceof ApiError
            ? failure
            : new ApiError(
                0,
                "unexpected_error",
                "Unable to confirm your update. Retry the same request.",
              );
        setError(safe);
        setUncertain(
          safe.status === 0 ||
            safe.status >= 500 ||
            safe.code === "invalid_response",
        );
        if ([403, 404, 409].includes(safe.status))
          await invalidateTickets(client, session);
      } finally {
        busy.current = false;
      }
    },
  };
}
export type TicketWrite = ReturnType<typeof useTicketWrite>;
