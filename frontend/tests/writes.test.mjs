import assert from "node:assert/strict";
import test from "node:test";
import { createApi } from "../src/api/client.ts";
import {
  buildWrite,
  operations,
  emptyDraft,
  WriteAttempt,
} from "../src/state/writes.ts";

const id = "11111111-1111-4111-8111-111111111111";
const ticket = {
  id,
  requester_id: id,
  assignee_id: id,
  title: "Synthetic",
  body: "Synthetic",
  status: "in_progress",
  priority: "normal",
  version: 4,
  archived: false,
  created_at: "2026-10-27T00:00:00Z",
  updated_at: "2026-10-27T00:00:00Z",
};
test("role and state choices exclude requester staff actions and archived writes", () => {
  assert.deepEqual(operations(ticket, "requester"), ["public"]);
  assert.deepEqual(operations({ ...ticket, archived: true }, "manager"), [
    "unarchive",
  ]);
  assert.deepEqual(operations({ ...ticket, archived: true }, "agent"), []);
  assert.ok(
    !operations({ ...ticket, status: "closed" }, "manager").includes("public"),
  );
  assert.throws(() =>
    buildWrite(
      ticket,
      "requester",
      { ...emptyDraft, operation: "internal", text: "private" },
      4,
    ),
  );
});
test("resolution includes its public reply atomically and keeps the original expected version", () => {
  assert.deepEqual(
    buildWrite(
      ticket,
      "agent",
      {
        ...emptyDraft,
        operation: "resolve",
        text: " Resolved with synthetic steps ",
      },
      3,
    ),
    {
      kind: "patch",
      body: {
        expected_version: 3,
        status: "resolved",
        public_reply: "Resolved with synthetic steps",
      },
    },
  );
});
test("reopen reason is public, bounded and separate from internal messages", () => {
  const resolved = { ...ticket, status: "resolved" };
  assert.deepEqual(
    buildWrite(
      resolved,
      "requester",
      { ...emptyDraft, operation: "reopen", text: "Still reproducible" },
      4,
    ),
    {
      kind: "patch",
      body: {
        expected_version: 4,
        status: "in_progress",
        reason: "Still reproducible",
      },
    },
  );
  assert.throws(() =>
    buildWrite(
      resolved,
      "requester",
      { ...emptyDraft, operation: "reopen", text: "x".repeat(2001) },
      4,
    ),
  );
  assert.throws(() =>
    buildWrite(ticket, "agent", { ...emptyDraft, text: "  " }, 4),
  );
});
test("unchanged retries reuse keys; payload, operation and reviewed version changes replace them", () => {
  const attempt = new WriteAttempt();
  const payload = { expected_version: 4, body: "Synthetic" };
  const key = attempt.key("message", payload);
  assert.equal(attempt.key("message", { ...payload }), key);
  assert.notEqual(attempt.key("message", { ...payload, body: "Changed" }), key);
  const changed = attempt.key("message", { ...payload, expected_version: 5 });
  assert.notEqual(changed, key);
  assert.notEqual(
    attempt.key("patch", { ...payload, expected_version: 5 }),
    changed,
  );
  const latest = attempt.key("message", payload);
  attempt.clear();
  assert.notEqual(attempt.key("message", payload), latest);
});
test("typed write API uses PATCH/POST, bearer and idempotency headers and validates responses", async () => {
  const captured = [];
  const api = createApi(async (url, options) => {
    captured.push({ url, options });
    return new Response(
      JSON.stringify(
        url.endsWith("/messages")
          ? {
              ticket_version: 5,
              message: {
                id,
                author_id: id,
                visibility: "public",
                body: "Reply",
                created_at: ticket.created_at,
              },
            }
          : ticket,
      ),
      { status: 200 },
    );
  });
  await api.patchTicket(
    id,
    "synthetic-token",
    { expected_version: 4, priority: "high" },
    "stable-key",
  );
  await api.createTicket(
    "synthetic-token",
    { title: "Synthetic", body: "Synthetic" },
    "create-key",
  );
  await api.message(
    id,
    "synthetic-token",
    { expected_version: 4, body: "Reply", visibility: "public" },
    "reply-key",
  );
  assert.deepEqual(
    captured.map((row) => row.options.method),
    ["PATCH", "POST", "POST"],
  );
  assert.deepEqual(
    captured.map((row) => row.options.headers["Idempotency-Key"]),
    ["stable-key", "create-key", "reply-key"],
  );
  assert.ok(
    captured.every(
      (row) =>
        row.options.headers.Authorization === "Bearer synthetic-token" &&
        !row.url.includes("token"),
    ),
  );
});
test("directory rejects overbroad roles and removes secret fields", async () => {
  let role = "agent";
  const api = createApi(
    async () =>
      new Response(
        JSON.stringify([
          {
            id,
            email: "agent@example.invalid",
            role,
            password_hash: "synthetic-hidden",
          },
        ]),
      ),
  );
  assert.deepEqual(await api.agents("token"), [
    { id, email: "agent@example.invalid", role: "agent" },
  ]);
  role = "manager";
  await assert.rejects(
    api.agents("token"),
    (error) => error.code === "invalid_response",
  );
});
