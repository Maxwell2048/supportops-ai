import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";

const password = "S09-local-synthetic-only!";

test("a real worker completes a no-evidence job for human review", async ({ page, request }) => {
  const login = await request.post("/api/auth/login", { data: { email: "requester-a@example.invalid", password } });
  expect(login.status()).toBe(200);
  const token = (await login.json()).access_token;
  const created = await request.post("/api/tickets", {
    headers: { Authorization: `Bearer ${token}`, "Idempotency-Key": randomUUID() },
    data: { title: `Unmatched synthetic request ${randomUUID()}`, body: "Synthetic request for a real worker." },
  });
  expect(created.status()).toBe(201);
  const ticketId = (await created.json()).id;
  await page.goto(`/#/tickets/${ticketId}`);
  await page.getByLabel("Email address").fill("manager@example.invalid");
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const panel = page.getByRole("region", { name: "Suggested response" });
  await panel.getByRole("button", { name: "Run analysis" }).click();
  await expect(panel.getByText("Human follow-up needed")).toBeVisible({ timeout: 20000 });
  await expect(panel.getByText("No model invoked")).toBeVisible();
  await expect(panel.getByRole("button", { name: "Approve and send" })).toBeDisabled();
  await panel.getByRole("button", { name: "Reject suggestion" }).click();
  await expect(page.getByText("Reviewed · rejected")).toBeVisible();
  await expect(page.getByText("There are no replies to this request yet.")).toBeVisible();
});

test("published knowledge reaches the worker and a human sends a reviewed reply", async ({ page, request }) => {
  async function tokenFor(email: string) {
    const response = await request.post("/api/auth/login", { data: { email, password } });
    expect(response.status()).toBe(200);
    return (await response.json()).access_token as string;
  }
  const requester = await tokenFor("requester-a@example.invalid");
  const manager = await tokenFor("manager@example.invalid");
  const title = "Sample access resolution";
  const created = await request.post("/api/tickets", {
    headers: { Authorization: `Bearer ${requester}`, "Idempotency-Key": randomUUID() },
    data: { title, body: "Synthetic case for reviewing a cited answer." },
  });
  expect(created.status()).toBe(201);
  const ticketId = (await created.json()).id;
  async function knowledge(path: string, data: unknown) {
    const response = await request.post(`/api/knowledge${path}`, {
      headers: { Authorization: `Bearer ${manager}`, "Idempotency-Key": randomUUID() }, data,
    });
    expect([200, 201]).toContain(response.status());
    return response.json();
  }
  const article = await knowledge("/articles", { title, body: "Synthetic guidance: verify the sample account before changing access.",
    scope: "support", source_kind: "synthetic", source_reference: "synthetic/worker-e2e", license_note: "Synthetic fixture" });
  await knowledge(`/articles/${article.id}/index`, { version_id: article.version.id, expected_revision: 1, mode: "keyword" });
  await knowledge(`/articles/${article.id}/publish`, { version_id: article.version.id, expected_revision: 1 });
  await page.goto(`/#/tickets/${ticketId}`);
  await page.getByLabel("Email address").fill("manager@example.invalid");
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const panel = page.getByRole("region", { name: "Suggested response" });
  await panel.getByRole("button", { name: "Run analysis" }).click();
  await expect(panel.getByText("Synthetic guidance: verify the sample account before changing access.")).toBeVisible({ timeout: 20000 });
  await expect(panel.getByText("Demo provider")).toBeVisible();
  await panel.getByLabel("Response draft").fill("I verified the sample account. Please try signing in again.");
  const reviewed = page.waitForResponse((response) => response.url().includes("/api/suggestions/") && response.url().endsWith("/review") && response.request().method() === "POST");
  await panel.getByRole("button", { name: "Send edited reply" }).click();
  expect((await reviewed).status()).toBe(200);
  await expect(page.locator(".message-public").getByText("I verified the sample account. Please try signing in again.")).toBeVisible();
  const response = await request.get(`/api/tickets/${ticketId}`, { headers: { Authorization: `Bearer ${requester}` } });
  expect(response.status()).toBe(200);
  const messages = (await response.json()).messages;
  expect(messages).toHaveLength(1);
  expect(messages[0].body).toBe("I verified the sample account. Please try signing in again.");
  await knowledge(`/articles/${article.id}/archive`, { version_id: article.version.id, expected_revision: 2 });
});
