import type {
  Role,
  TicketSummary,
  TicketPatch,
  MessageCreate,
} from "../api/contracts.ts";

export type Operation =
  | "public"
  | "internal"
  | "start"
  | "wait"
  | "resolve"
  | "reopen"
  | "close"
  | "assign"
  | "priority"
  | "archive"
  | "unarchive";
export interface Draft {
  operation: Operation;
  text: string;
  assignee: string;
  priority: string;
}
export const emptyDraft: Draft = {
  operation: "public",
  text: "",
  assignee: "",
  priority: "normal",
};
export function operations(ticket: TicketSummary, role: Role): Operation[] {
  if (ticket.archived) return role === "manager" ? ["unarchive"] : [];
  const result: Operation[] =
    ticket.status === "closed"
      ? []
      : role === "requester"
        ? ["public"]
        : ["public", "internal"];
  if (role !== "requester") {
    if (ticket.status === "open" || ticket.status === "waiting_customer")
      result.push("start");
    if (ticket.status === "in_progress") result.push("wait", "resolve");
    if (ticket.status === "waiting_customer") result.push("resolve");
  }
  if (ticket.status === "resolved") result.push("reopen");
  if (role === "manager") {
    result.push("assign", "priority");
    if (ticket.status === "resolved") result.push("close");
    if (ticket.status === "closed") result.push("reopen", "archive");
  }
  return result;
}
export function needsText(operation: Operation) {
  return ["public", "internal", "wait", "resolve", "reopen"].includes(
    operation,
  );
}
export function buildWrite(
  ticket: TicketSummary,
  role: Role,
  draft: Draft,
  version: number,
):
  | { kind: "message"; body: MessageCreate }
  | { kind: "patch"; body: TicketPatch } {
  if (!operations(ticket, role).includes(draft.operation))
    throw new Error(
      "This operation is no longer available. Choose another action.",
    );
  const text = draft.text.trim();
  if (
    needsText(draft.operation) &&
    (!text ||
      text.includes("\0") ||
      [...text].length > (draft.operation === "reopen" ? 2000 : 10000))
  )
    throw new Error("Enter valid text within the displayed limit.");
  const body: TicketPatch = { expected_version: version };
  switch (draft.operation) {
    case "public":
    case "internal":
      return {
        kind: "message",
        body: {
          expected_version: version,
          visibility: draft.operation,
          body: text,
        },
      };
    case "assign":
      body.assignee_id = draft.assignee || null;
      break;
    case "priority":
      body.priority = draft.priority as TicketPatch["priority"];
      break;
    case "archive":
      body.archived = true;
      break;
    case "unarchive":
      body.archived = false;
      break;
    case "start":
      body.status = "in_progress";
      break;
    case "wait":
      body.status = "waiting_customer";
      body.public_reply = text;
      break;
    case "resolve":
      body.status = "resolved";
      body.public_reply = text;
      break;
    case "close":
      body.status = "closed";
      break;
    case "reopen":
      body.status = ticket.status === "closed" ? "open" : "in_progress";
      body.reason = text;
      break;
  }
  return { kind: "patch", body };
}
// Keep the exact body and key together, including after an ambiguous transport failure.
export class WriteAttempt {
  private last: { fingerprint: string; key: string } | null = null;
  key(operation: string, payload: unknown) {
    const fingerprint = JSON.stringify([operation, payload]);
    if (this.last?.fingerprint !== fingerprint)
      this.last = { fingerprint, key: crypto.randomUUID() };
    return this.last.key;
  }
  clear() {
    this.last = null;
  }
}
