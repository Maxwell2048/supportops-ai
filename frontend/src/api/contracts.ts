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
}
export interface TicketPage {
  items: TicketSummary[];
  next_cursor: string | null;
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
  return { ...parseTicket(value), messages, events };
}
