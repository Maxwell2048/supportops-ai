import assert from "node:assert/strict";
import test from "node:test";
import { ApiError, createApi } from "../src/api/client.ts";

const id = "11111111-1111-4111-8111-111111111111";
const requestId = "22222222-2222-4222-8222-222222222222";
const ticket = {
  id,
  requester_id: id,
  assignee_id: null,
  title: "Synthetic ticket",
  body: "Synthetic description",
  status: "open",
  priority: "normal",
  version: 1,
  archived: false,
  created_at: "2026-10-27T01:00:00Z",
  updated_at: "2026-10-27T01:00:00Z",
};
const json = (body, status = 200, headers = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      "X-Request-ID": requestId,
      ...headers,
    },
  });

test("login normalizes email, sends credentials only in the body, and forbids redirects/cookies/cache", async () => {
  let captured;
  const api = createApi(async (url, init) => {
    captured = { url, init };
    return json({
      access_token: "synthetic-token",
      token_type: "bearer",
      expires_in: 900,
    });
  });
  await api.login(" Demo@Example.invalid ", "synthetic-password");
  assert.equal(captured.url, "/api/auth/login");
  assert.deepEqual(JSON.parse(captured.init.body), {
    email: "demo@example.invalid",
    password: "synthetic-password",
  });
  assert.equal(captured.init.headers.Authorization, undefined);
  assert.equal(captured.init.credentials, "omit");
  assert.equal(captured.init.cache, "no-store");
  assert.equal(captured.init.redirect, "error");
});

test("protected calls keep bearer tokens out of URLs and strip unrecognized account fields", async () => {
  const api = createApi(async (url, init) => {
    assert.equal(url, "/api/me");
    assert.equal(init.headers.Authorization, "Bearer synthetic-token");
    return json({
      id,
      email: "demo@example.invalid",
      role: "manager",
      password_hash: "must-not-be-kept",
    });
  });
  assert.deepEqual(await api.me("synthetic-token"), {
    id,
    email: "demo@example.invalid",
    role: "manager",
  });
});

test("cursor is encoded as a query parameter rather than interpolated as URL syntax", async () => {
  const cursor = "opaque+cursor&other=private";
  const api = createApi(async (url) => {
    const parsed = new URL(url, "http://localhost");
    assert.equal(parsed.searchParams.get("cursor"), cursor);
    assert.equal(parsed.searchParams.has("other"), false);
    return json({ items: [ticket], next_cursor: null });
  });
  assert.equal((await api.tickets("synthetic-token", cursor)).items.length, 1);
});

test("requester projection excludes internal messages and events even in an overbroad response", async () => {
  const message = {
    id,
    author_id: id,
    body: "Synthetic message",
    created_at: ticket.created_at,
  };
  const api = createApi(async () =>
    json({
      ...ticket,
      messages: [
        { ...message, visibility: "public" },
        { ...message, visibility: "internal" },
      ],
      events: [
        {
          id,
          actor_id: id,
          event_type: "created",
          ticket_version: 1,
          created_at: ticket.created_at,
        },
      ],
    }),
  );
  const detail = await api.ticket(id, "synthetic-token", "requester");
  assert.equal(detail.messages.length, 1);
  assert.equal(detail.messages[0].visibility, "public");
  assert.equal("events" in detail, false);
  assert.equal(
    (await api.ticket(id, "synthetic-token", "agent")).messages.length,
    2,
  );
  assert.equal(
    (await api.ticket(id, "synthetic-token", "manager")).events.length,
    1,
  );
});

for (const status of [401, 403, 404, 409, 422, 429, 503]) {
  test(`HTTP ${status} exposes a safe message and the server request ID`, async () => {
    const api = createApi(async () =>
      json(
        {
          error: {
            code: "synthetic_error",
            message: "SECRET proxy input",
            details: { password: "SECRET" },
          },
        },
        status,
        { "Retry-After": "60" },
      ),
    );
    await assert.rejects(api.me("synthetic-token"), (error) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.status, status);
      assert.equal(error.requestId, requestId);
      assert.equal(error.message.includes("SECRET"), false);
      assert.equal(error.retryAfter, status === 429 ? 60 : null);
      return true;
    });
  });
}

test("malformed success DTOs cannot silently become application state", async () => {
  for (const invalid of [
    { items: [{ ...ticket, version: true }], next_cursor: null },
    { items: [{ ...ticket, status: "unknown" }], next_cursor: null },
    { items: [ticket], next_cursor: 123 },
  ]) {
    const api = createApi(async () => json(invalid));
    await assert.rejects(
      api.tickets("synthetic-token", null),
      (error) =>
        error.code === "invalid_response" && error.requestId === requestId,
    );
  }
});

test("HTML proxy responses and invalid request IDs are not reflected", async () => {
  const api = createApi(
    async () =>
      new Response("<html>SECRET proxy details</html>", {
        status: 502,
        headers: { "X-Request-ID": "untrusted-value" },
      }),
  );
  await assert.rejects(
    api.me("synthetic-token"),
    (error) =>
      error.status === 502 &&
      error.requestId === null &&
      !error.message.includes("SECRET"),
  );
});

test("invalid local ticket addresses never send a request", async () => {
  const api = createApi(async () => {
    assert.fail("Must not fetch invalid IDs");
  });
  await assert.rejects(
    api.ticket("../../me?token=secret", "synthetic-token", "requester"),
    (error) => error.status === 404,
  );
});

test("aborted callers do not issue requests or become network errors", async () => {
  const controller = new AbortController();
  controller.abort();
  const api = createApi(async () => {
    assert.fail("Must not fetch an aborted request");
  });
  await assert.rejects(
    api.me("synthetic-token", controller.signal),
    (error) => error.name === "AbortError",
  );
});

test("request timeouts abort the fetch and report a retryable safe failure", async () => {
  const api = createApi(
    async (_url, init) =>
      new Promise((_resolve, reject) =>
        init.signal.addEventListener("abort", () =>
          reject(new DOMException("aborted", "AbortError")),
        ),
      ),
    15,
  );
  await assert.rejects(
    api.me("synthetic-token"),
    (error) => error.code === "timeout" && error.status === 0,
  );
});

test("transport failures do not reveal exception details", async () => {
  const api = createApi(async () => {
    throw new Error("SECRET local network details");
  });
  await assert.rejects(
    api.me("synthetic-token"),
    (error) =>
      error.code === "network_error" && !error.message.includes("SECRET"),
  );
});
