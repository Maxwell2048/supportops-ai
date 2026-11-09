import type { Priority, TicketStatus } from "../api/contracts.ts";
import { isUuid } from "../api/contracts.ts";
import { ApiError } from "../api/client.ts";

export interface TicketFilters {
  q: string;
  status: TicketStatus | "";
  priority: Priority | "";
}
export const emptyFilters: TicketFilters = { q: "", status: "", priority: "" };
export function normalizeFilters(input: {
  q?: string;
  status?: string;
  priority?: string;
}): TicketFilters {
  const q = (input.q ?? "").trim(),
    status = input.status ?? "",
    priority = input.priority ?? "";
  if (
    q.length > 200 ||
    q.includes("\0") ||
    ![
      "",
      "open",
      "in_progress",
      "waiting_customer",
      "resolved",
      "closed",
    ].includes(status) ||
    !["", "low", "normal", "high", "urgent"].includes(priority)
  ) {
    throw new ApiError(
      422,
      "invalid_filters",
      "The ticket filters are invalid. Clear the filters and try again.",
    );
  }
  return {
    q,
    status: status as TicketFilters["status"],
    priority: priority as TicketFilters["priority"],
  };
}
export function filterKey(filters: TicketFilters) {
  return JSON.stringify(normalizeFilters(filters));
}
export function listHref(filters: TicketFilters) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(normalizeFilters(filters)))
    if (value) params.set(key, value);
  return "#/tickets" + (params.size ? "?" + params.toString() : "");
}
export function routeFromHash(hash: string) {
  const [path, query = ""] = (hash.slice(1) || "/tickets").split("?");
  if (path === "/knowledge" && !query) return { kind: "knowledge" as const };
  if (path === "/tickets/new" && !query) return { kind: "create" as const };
  if (path === "/tickets" || path === "/") {
    try {
      const params = new URLSearchParams(query);
      for (const key of params.keys())
        if (!["q", "status", "priority"].includes(key))
          throw new Error("Unknown filter");
      return {
        kind: "list" as const,
        filters: normalizeFilters(Object.fromEntries(params)),
      };
    } catch {
      return {
        kind: "missing" as const,
        error: new ApiError(
          422,
          "invalid_filters",
          "This filter address is invalid. Return to the unfiltered list.",
        ),
      };
    }
  }
  const match = /^\/tickets\/([^/]+)$/.exec(path);
  if (match && isUuid(match[1]) && !query)
    return { kind: "detail" as const, id: match[1] };
  return {
    kind: "missing" as const,
    error: new ApiError(
      404,
      "not_found",
      "This page address is not available. Return to your tickets.",
    ),
  };
}
