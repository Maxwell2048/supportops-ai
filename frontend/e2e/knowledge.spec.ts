import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";

test("real knowledge publication keeps immutable versions and rechecks historical scope", async ({
  request,
}) => {
  async function auth(label: string) {
    const response = await request.post("/api/auth/login", {
      data: {
        email: `${label}@example.invalid`,
        password: "S09-local-synthetic-only!",
      },
    });
    expect(response.status()).toBe(200);
    return { Authorization: `Bearer ${(await response.json()).access_token}` };
  }
  const manager = await auth("manager"),
    agent = await auth("agent-a"),
    requester = await auth("requester-b");
  async function post(path: string, body: unknown, key = randomUUID()) {
    const response = await request.post("/api/knowledge" + path, {
      headers: { ...manager, "Idempotency-Key": key },
      data: body,
    });
    expect([200, 201]).toContain(response.status());
    return response.json();
  }
  const content = {
    title: `[S13 E2E] ${randomUUID()}`,
    body: "Original synthetic source text.",
    scope: "support",
    source_kind: "synthetic",
    source_reference: "supportops.synthetic/e2e/v1",
    license_note: "Original synthetic test content; no external data.",
  };
  const first = await post("/articles", content);
  const articlePath = `/api/knowledge/articles/${first.id}`,
    versionPath = `/api/knowledge/versions/${first.version.id}`;
  expect((await request.get(versionPath, { headers: agent })).status()).toBe(
    404,
  );
  expect(
    (
      await request.get("/api/knowledge/articles", { headers: requester })
    ).status(),
  ).toBe(403);
  const publishBody = { version_id: first.version.id, expected_revision: 1 },
    publishKey = randomUUID();
  await post(`/articles/${first.id}/publish`, publishBody, publishKey);
  expect((await request.get(versionPath, { headers: agent })).status()).toBe(
    200,
  );
  const restricted = await post("/articles", {
    ...content,
    article_id: first.id,
    expected_revision: 2,
    scope: "management",
    body: "Restricted synthetic management source.",
  });
  expect(
    (
      await request.get(`/api/knowledge/versions/${restricted.version.id}`, {
        headers: agent,
      })
    ).status(),
  ).toBe(404);
  await post(`/articles/${first.id}/publish`, {
    version_id: restricted.version.id,
    expected_revision: 3,
  });
  expect((await request.get(versionPath, { headers: agent })).status()).toBe(
    404,
  );
  const newer = await post("/articles", {
    ...content,
    article_id: first.id,
    expected_revision: 4,
    body: "Newer synthetic support source.",
  });
  await post(`/articles/${first.id}/publish`, {
    version_id: newer.version.id,
    expected_revision: 5,
  });
  const historical = await request.get(versionPath, { headers: agent });
  expect(historical.status()).toBe(200);
  expect(await historical.json()).toMatchObject({
    body: content.body,
    content_hash: first.version.content_hash,
    status: "archived",
  });
  await post(`/articles/${first.id}/archive`, {
    version_id: newer.version.id,
    expected_revision: 6,
  });
  expect((await request.get(versionPath, { headers: agent })).status()).toBe(
    404,
  );
  // Replaying an old successful publication is a receipt, not a new publication command.
  await post(`/articles/${first.id}/publish`, publishBody, publishKey);
  const current = await request.get(articlePath, { headers: manager });
  expect(await current.json()).toMatchObject({
    revision: 7,
    archived: true,
    published_version_id: newer.version.id,
  });
  const audit = await request.get(articlePath + "/events", {
    headers: manager,
  });
  expect(audit.status()).toBe(200);
  const events = (await audit.json()).items;
  expect(events).toHaveLength(7);
  expect(
    events.map((row: { article_revision: number }) => row.article_revision),
  ).toEqual([1, 2, 3, 4, 5, 6, 7]);
  expect(JSON.stringify(events)).not.toContain(content.body);
});
