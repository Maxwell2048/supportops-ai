import {
  MutationCache,
  QueryCache,
  QueryClient,
  queryOptions,
} from "@tanstack/react-query";
import { api, ApiError } from "../api/client.ts";
import type { Role } from "../api/contracts.ts";
import { normalizeFilters } from "./ticketState.ts";
import type { TicketFilters } from "./ticketState.ts";

export interface QuerySession {
  key: string;
  token: string;
  user: { id: string; role: Role };
}
export function createSessionClient(onExpired: () => void = () => {}) {
  return new QueryClient({
    mutationCache: new MutationCache({
      onError: (error) => {
        if (error instanceof ApiError && error.status === 401) onExpired();
      },
    }),
    queryCache: new QueryCache({
      onError: (error) => {
        if (error instanceof ApiError && error.status === 401) onExpired();
      },
    }),
    defaultOptions: {
      mutations: { retry: false, networkMode: "always" },
      queries: {
        staleTime: 15_000,
        gcTime: 120_000,
        retry: false,
        networkMode: "always",
        refetchOnMount: "always",
        refetchOnWindowFocus: "always",
        refetchOnReconnect: "always",
      },
    },
  });
}
export function ticketRoot(session: QuerySession) {
  return [
    "session",
    session.key,
    session.user.id,
    session.user.role,
    "tickets",
  ] as const;
}
export function listOptions(
  session: QuerySession,
  filters: TicketFilters,
  cursor: string | null,
) {
  const normalized = normalizeFilters(filters);
  return queryOptions({
    queryKey: [
      ...ticketRoot(session),
      "list",
      { filters: normalized, cursor, limit: 20 },
    ] as const,
    queryFn: ({ signal }) =>
      api.tickets(session.token, cursor, signal, normalized),
  });
}
export function detailOptions(session: QuerySession, id: string) {
  return queryOptions({
    queryKey: [...ticketRoot(session), "detail", id] as const,
    queryFn: ({ signal }) =>
      api.ticket(id, session.token, session.user.role, signal),
  });
}
export function invalidateTickets(client: QueryClient, session: QuerySession) {
  return client.invalidateQueries({ queryKey: ticketRoot(session) });
}
export type Remote<T> =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "success"; data: T };
export function queryView<T>(query: {
  isPending: boolean;
  isFetching: boolean;
  isError: boolean;
  error: unknown;
  data: T | undefined;
}): Remote<T> {
  // Never present cached content as currently authorized while revalidation is running or failed.
  if (query.isPending || query.isFetching) return { status: "loading" };
  if (query.isError)
    return {
      status: "error",
      error:
        query.error instanceof ApiError
          ? query.error
          : new ApiError(
              0,
              "unexpected_error",
              "Unable to load the latest data. Please try again.",
            ),
    };
  return query.data === undefined
    ? { status: "loading" }
    : { status: "success", data: query.data };
}
