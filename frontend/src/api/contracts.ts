export type Role = "requester" | "agent" | "manager";
export type TicketStatus =
  | "open"
  | "in_progress"
  | "waiting_customer"
  | "resolved"
  | "closed";
export type Priority = "low" | "normal" | "high" | "urgent";

export interface User {
  id: string;
  email: string;
  role: Role;
}
export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}
export interface TicketSummary {
  id: string;
  requester_id: string;
  assignee_id: string | null;
  title: string;
  body: string;
  contact_phone?: string | null;
  status: TicketStatus;
  priority: Priority;
  version: number;
  archived: boolean;
  created_at: string;
  updated_at: string;
}
export interface TicketMessage {
  id: string;
  author_id: string;
  visibility: "public" | "internal";
  body: string;
  created_at: string;
}
export interface TicketEvent {
  id: string;
  actor_id: string;
  event_type: string;
  ticket_version: number;
  created_at: string;
}
export interface TicketDetail extends TicketSummary {
  messages: TicketMessage[];
  events?: TicketEvent[];
  requester_email?: string;
}
export interface TicketPage {
  items: TicketSummary[];
  next_cursor: string | null;
}

export interface TicketPatch {
  expected_version: number;
  status?: TicketStatus;
  priority?: Priority;
  assignee_id?: string | null;
  archived?: boolean;
  reason?: string;
  public_reply?: string;
}
export interface MessageCreate {
  expected_version: number;
  visibility: "public" | "internal";
  body: string;
}
export function parseAgents(value: unknown): User[] {
  return array(value, (item) => {
    const user = parseUser(item);
    if (user.role !== "agent") throw new Error("Invalid directory role");
    return user;
  });
}
export function parseMessageWrite(value: unknown) {
  const row = record(value),
    message = record(row.message);
  return {
    ticket_version: integer(row.ticket_version),
    message: {
      id: uuid(message.id),
      author_id: uuid(message.author_id),
      visibility: choice(message.visibility, ["public", "internal"] as const),
      body: text(message.body),
      created_at: timestamp(message.created_at),
    },
  };
}

export const isUuid = (value: string) =>
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("Invalid object");
  return value as Record<string, unknown>;
}
function text(value: unknown): string {
  if (typeof value !== "string") throw new Error("Invalid text");
  return value;
}
function uuid(value: unknown): string {
  const result = text(value);
  if (!isUuid(result)) throw new Error("Invalid identifier");
  return result;
}
function integer(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 1)
    throw new Error("Invalid integer");
  return value;
}
function timestamp(value: unknown): string {
  const result = text(value);
  if (
    !result.includes("T") ||
    !/(Z|[+-]\d{2}:\d{2})$/.test(result) ||
    !Number.isFinite(Date.parse(result))
  )
    throw new Error("Invalid timestamp");
  return result;
}
function choice<T extends string>(value: unknown, allowed: readonly T[]): T {
  if (!allowed.includes(value as T)) throw new Error("Invalid choice");
  return value as T;
}
function array<T>(value: unknown, parse: (item: unknown) => T): T[] {
  if (!Array.isArray(value)) throw new Error("Invalid array");
  return value.map(parse);
}

export function parseUser(value: unknown): User {
  const row = record(value);
  return {
    id: uuid(row.id),
    email: text(row.email),
    role: choice(row.role, ["requester", "agent", "manager"]),
  };
}
export function parseToken(value: unknown): TokenResponse {
  const row = record(value),
    token = text(row.access_token),
    ttl = integer(row.expires_in);
  if (!token || /\s/.test(token) || ttl > 1800)
    throw new Error("Invalid token response");
  return {
    access_token: token,
    token_type: choice(row.token_type, ["bearer"]),
    expires_in: ttl,
  };
}
export function parseTicket(value: unknown): TicketSummary {
  const row = record(value);
  if (typeof row.archived !== "boolean")
    throw new Error("Invalid archive flag");
  return {
    id: uuid(row.id),
    requester_id: uuid(row.requester_id),
    assignee_id: row.assignee_id === null ? null : uuid(row.assignee_id),
    title: text(row.title),
    body: text(row.body),
    contact_phone: row.contact_phone == null ? null : text(row.contact_phone),
    version: integer(row.version),
    archived: row.archived,
    status: choice(row.status, [
      "open",
      "in_progress",
      "waiting_customer",
      "resolved",
      "closed",
    ]),
    priority: choice(row.priority, ["low", "normal", "high", "urgent"]),
    created_at: timestamp(row.created_at),
    updated_at: timestamp(row.updated_at),
  };
}
export function parsePage(value: unknown): TicketPage {
  const row = record(value);
  const cursor = row.next_cursor === null ? null : text(row.next_cursor);
  if (cursor !== null && (!cursor || cursor.length > 4096))
    throw new Error("Invalid cursor");
  return { items: array(row.items, parseTicket), next_cursor: cursor };
}
export function parseDetail(value: unknown, role: Role): TicketDetail {
  const row = record(value);
  const messages = array(row.messages, (item) => {
    const message = record(item);
    return {
      id: uuid(message.id),
      author_id: uuid(message.author_id),
      visibility: choice(message.visibility, ["public", "internal"] as const),
      body: text(message.body),
      created_at: timestamp(message.created_at),
    };
  });
  // This is display defense only. The API independently enforces object/field access.
  if (role === "requester")
    return {
      ...parseTicket(value),
      messages: messages.filter((item) => item.visibility === "public"),
    };
  const events =
    row.events === undefined
      ? undefined
      : array(row.events, (item) => {
          const event = record(item);
          return {
            id: uuid(event.id),
            actor_id: uuid(event.actor_id),
            event_type: text(event.event_type),
            ticket_version: integer(event.ticket_version),
            created_at: timestamp(event.created_at),
          };
        });
  return { ...parseTicket(value), messages, events,
    requester_email: row.requester_email === undefined ? undefined : text(row.requester_email) };
}

export function parseAnalysisJobs(value: unknown) {
  return array(value, (item) => {
    const row = record(item);
    if (typeof row.attempts !== "number" || !Number.isInteger(row.attempts) || row.attempts < 0 || row.attempts > 3) throw new Error("Invalid attempts");
    return {
      job_id: uuid(row.job_id),
      status: choice(row.status, ["queued", "running", "succeeded", "failed"] as const),
      attempts: row.attempts,
      error_code: row.error_code === null ? null : text(row.error_code),
      review_decision: row.review_decision === null ? null : choice(row.review_decision, ["accepted", "edited", "rejected"] as const),
    };
  });
}

export function parseAnalysisReceipt(value: unknown) {
  const row = record(value);
  return { job_id: uuid(row.job_id), status: choice(row.status, ["queued"] as const) };
}

export function parseSuggestion(value: unknown) {
  const row = record(value), suggestion = record(row.suggestion);
  const generation = row.generation == null ? null : record(row.generation);
  return {
    job_id: uuid(row.job_id), ticket_version: integer(row.ticket_version),
    review_decision: row.review_decision === null ? null : choice(row.review_decision, ["accepted", "edited", "rejected"] as const),
    generation: generation === null ? null : {
      provider: generation.provider == null ? null : choice(generation.provider, ["none", "mock", "ollama", "custom"] as const),
      model: generation.model == null ? null : text(generation.model),
      digest: generation.digest == null ? null : text(generation.digest),
    },
    tool_calls: row.tool_calls == null ? [] : array(row.tool_calls, (item) => {
      const call = record(item);
      const args = call.arguments == null ? null : record(call.arguments);
      return {
        tool: text(call.tool),
        planner: choice(call.planner, ["model", "system"] as const),
        status: choice(call.status, ["ok", "rejected", "budget_exceeded", "stopped"] as const),
        reason: call.reason == null ? null : text(call.reason),
        result_count: typeof call.result_count === "number" && Number.isSafeInteger(call.result_count) && call.result_count >= 0 ? call.result_count : 0,
        query: args && typeof args.query === "string" ? args.query : null,
      };
    }),
    suggestion: {
      category: choice(suggestion.category, ["access", "billing", "bug", "how_to", "other"] as const),
      suggested_priority: choice(suggestion.suggested_priority, ["low", "normal", "high", "urgent"] as const),
      reply_draft: text(suggestion.reply_draft),
      citations: array(suggestion.citations, (item) => { const citation = record(item); return { chunk_id: uuid(citation.chunk_id), version_id: uuid(citation.version_id), quote: text(citation.quote) }; }),
      human_verification: array(suggestion.human_verification, text),
    },
  };
}

export function parseReviewReceipt(value: unknown) {
  const row = record(value);
  return { job_id: uuid(row.job_id), decision: choice(row.decision, ["accepted", "edited", "rejected"] as const),
    message_id: row.message_id === null ? null : uuid(row.message_id), ticket_version: integer(row.ticket_version) };
}

export interface KnowledgeDraft {
  title: string;
  body: string;
  scope: "support" | "management";
  source_kind: "synthetic" | "licensed";
  source_reference: string;
  license_note: string;
  article_id?: string;
  expected_revision?: number;
}

export function parseKnowledgePage(value: unknown) {
  const row = record(value);
  return {
    items: array(row.items, (entry) => {
      const item = record(entry);
      return { article_id: uuid(item.article_id), version_id: uuid(item.version_id), number: integer(item.number),
        title: text(item.title), scope: choice(item.scope, ["support", "management"] as const),
        status: choice(item.status, ["draft", "published", "archived"] as const) };
    }),
    next_cursor: row.next_cursor === null ? null : text(row.next_cursor),
  };
}

export function parseKnowledgeArticle(value: unknown) {
  const row = record(value), version = record(row.version);
  if (typeof row.archived !== "boolean") throw new Error("Invalid archive state");
  return {
    id: uuid(row.id), revision: row.revision == null ? null : integer(row.revision),
    published_version_id: row.published_version_id == null ? null : uuid(row.published_version_id), archived: row.archived,
    version: { id: uuid(version.id), title: text(version.title), body: text(version.body), number: integer(version.number),
      scope: choice(version.scope, ["support", "management"] as const), source_kind: choice(version.source_kind, ["synthetic", "licensed"] as const),
      source_reference: text(version.source_reference), license_note: text(version.license_note),
      status: choice(version.status, ["draft", "published", "archived"] as const) },
  };
}

export function parseIndexReceipt(value: unknown) {
  const row = record(value);
  return { version_id: uuid(row.version_id), chunk_count: integer(row.chunk_count), mode: choice(row.mode, ["keyword", "vector"] as const) };
}
