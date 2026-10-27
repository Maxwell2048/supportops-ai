import {
  isUuid,
  parseDetail,
  parsePage,
  parseToken,
  parseUser,
  parseAgents,
  parseTicket,
  parseMessageWrite,
} from "./contracts.ts";
import type { Role, TicketPatch, MessageCreate } from "./contracts.ts";
import type { TicketFilters } from "../state/ticketState.ts";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;
  readonly retryAfter: number | null;
  constructor(
    status: number,
    code: string,
    message: string,
    requestId: string | null = null,
    retryAfter: number | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.retryAfter = retryAfter;
  }
}

interface Options {
  method?: "POST" | "PATCH";
  key?: string;
  token?: string;
  body?: unknown;
  signal?: AbortSignal;
}

export function createApi(fetcher: typeof fetch = fetch, timeoutMs = 15000) {
  async function request<T>(
    path: string,
    parse: (value: unknown) => T,
    options: Options = {},
  ): Promise<T> {
    const controller = new AbortController();
    let timedOut = false;
    const cancel = () => controller.abort();
    options.signal?.addEventListener("abort", cancel, { once: true });
    if (options.signal?.aborted) cancel();
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
    try {
      if (controller.signal.aborted)
        throw new DOMException("Request cancelled", "AbortError");
      const headers: Record<string, string> = { Accept: "application/json" };
      if (options.token) headers.Authorization = `Bearer ${options.token}`;
      if (options.key) headers["Idempotency-Key"] = options.key;
      if (options.body !== undefined)
        headers["Content-Type"] = "application/json";
      const response = await fetcher(`/api${path}`, {
        method: options.method ?? (options.body === undefined ? "GET" : "POST"),
        headers,
        body:
          options.body === undefined ? undefined : JSON.stringify(options.body),
        credentials: "omit",
        cache: "no-store",
        redirect: "error",
        signal: controller.signal,
      });
      const candidateId = response.headers.get("X-Request-ID");
      const requestId = candidateId && isUuid(candidateId) ? candidateId : null;
      let payload: unknown;
      try {
        payload = await response.json();
      } catch {
        payload = null;
      }
      if (controller.signal.aborted)
        throw new DOMException("Request cancelled", "AbortError");
      if (!response.ok) {
        let code = "http_error";
        if (payload && typeof payload === "object" && "error" in payload) {
          const error = payload.error;
          if (
            error &&
            typeof error === "object" &&
            "code" in error &&
            typeof error.code === "string" &&
            /^[a-z_]{1,64}$/.test(error.code)
          )
            code = error.code;
        }
        // Do not reflect arbitrary server/proxy bodies or credential-bearing error text.
        const messages: Record<number, string> = {
          401:
            path === "/auth/login"
              ? "Incorrect email or password."
              : "Your session has expired. Please sign in again.",
          403: "Your current role cannot access this resource.",
          404: "This ticket does not exist or is no longer available to you.",
          409: "The ticket has changed. Reload it before continuing.",
          422: "Some request fields are invalid. Check your input and try again.",
          429: "Too many sign-in attempts. Wait before trying again.",
        };
        const delay = Number(response.headers.get("Retry-After"));
        const fieldMessages: Record<string, string> = {
          assignee_unavailable:
            "This agent is no longer available. Refresh the agent list and choose an active agent.",
          no_changes: "Choose a value different from the current ticket value.",
          public_reply_required: "Enter a public reply for this status change.",
          reopen_reason_required:
            "Enter a public reason for reopening this ticket.",
        };
        throw new ApiError(
          response.status,
          code,
          (response.status === 422 ? fieldMessages[code] : undefined) ??
            messages[response.status] ??
            "The service is temporarily unavailable. Please try again.",
          requestId,
          response.status === 429 &&
          Number.isSafeInteger(delay) &&
          delay > 0 &&
          delay <= 3600
            ? delay
            : null,
        );
      }
      try {
        return parse(payload);
      } catch {
        throw new ApiError(
          response.status,
          "invalid_response",
          "The service returned an unexpected response. Please try again.",
          requestId,
        );
      }
    } catch (error) {
      if (options.signal?.aborted)
        throw new DOMException("Request cancelled", "AbortError");
      if (error instanceof ApiError) throw error;
      throw new ApiError(
        0,
        timedOut ? "timeout" : "network_error",
        timedOut
          ? "The request timed out. Please try again."
          : "Unable to reach the service. Check your connection and try again.",
      );
    } finally {
      clearTimeout(timer);
      options.signal?.removeEventListener("abort", cancel);
    }
  }
  return {
    agents: (token: string, signal?: AbortSignal) =>
      request("/agents", parseAgents, { token, signal }),
    createTicket: (
      token: string,
      body: { title: string; body: string },
      key: string,
      signal?: AbortSignal,
    ) => request("/tickets", parseTicket, { token, body, key, signal }),
    patchTicket: (
      id: string,
      token: string,
      body: TicketPatch,
      key: string,
      signal?: AbortSignal,
    ) =>
      request(`/tickets/${encodeURIComponent(id)}`, parseTicket, {
        token,
        body,
        key,
        signal,
        method: "PATCH",
      }),
    message: (
      id: string,
      token: string,
      body: MessageCreate,
      key: string,
      signal?: AbortSignal,
    ) =>
      request(
        `/tickets/${encodeURIComponent(id)}/messages`,
        parseMessageWrite,
        { token, body, key, signal },
      ),
    login: (email: string, password: string, signal?: AbortSignal) =>
      request("/auth/login", parseToken, {
        body: { email: email.trim().toLowerCase(), password },
        signal,
      }),
    me: (token: string, signal?: AbortSignal) =>
      request("/me", parseUser, { token, signal }),
    tickets: (
      token: string,
      cursor: string | null,
      signal?: AbortSignal,
      filters: Partial<TicketFilters> = {},
    ) =>
      request(
        `/tickets?${new URLSearchParams({ limit: "20", ...(cursor ? { cursor } : {}), ...(filters.q?.trim() ? { q: filters.q.trim() } : {}), ...(filters.status ? { status: filters.status } : {}), ...(filters.priority ? { priority: filters.priority } : {}) })}`,
        parsePage,
        { token, signal },
      ),
    ticket: (id: string, token: string, role: Role, signal?: AbortSignal) => {
      if (!isUuid(id))
        return Promise.reject(
          new ApiError(404, "not_found", "This ticket address is invalid."),
        );
      return request(
        `/tickets/${encodeURIComponent(id)}`,
        (value) => parseDetail(value, role),
        { token, signal },
      );
    },
  };
}

export const api = createApi();
