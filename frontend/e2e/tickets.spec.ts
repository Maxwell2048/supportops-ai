import { test, expect } from "@playwright/test";
import type { Browser, BrowserContext, Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const password = "S09-local-synthetic-only!";
const seedId = "704ad20c-bb80-535f-888e-f503a1656df0";
const contexts: BrowserContext[] = [];
test.afterEach(async () => {
  await Promise.all(contexts.splice(0).map((context) => context.close()));
});
test.beforeEach(async ({ page }) => {
  // Catch React/rendering exceptions instead of accepting a partly broken page.
  page.on("pageerror", (error) => {
    throw error;
  });
});
async function login(page: Page, label: string, hash = "/tickets") {
  await page.goto(`/#${hash}`);
  await page.getByLabel("Email address").fill(`${label}@example.invalid`);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Sign out", exact: true }),
  ).toBeVisible();
}
async function other(browser: Browser, page: Page, label: string, id: string) {
  const context = await browser.newContext({
    baseURL: "http://127.0.0.1:5174",
    viewport: page.viewportSize()!,
  });
  contexts.push(context);
  const result = await context.newPage();
  result.on("pageerror", (error) => {
    throw error;
  });
  await login(result, label, `/tickets/${id}`);
  await expect(result.getByLabel("Action", { exact: true })).toBeVisible();
  return result;
}
async function create(page: Page) {
  const title = `[S12 E2E] Synthetic ${randomUUID()}`;
  await page.getByRole("link", { name: "New request", exact: true }).click();
  await expect(page.getByLabel("Title", { exact: true })).toBeFocused();
  await page
    .getByRole("button", { name: "Submit request", exact: true })
    .click();
  await expect(page.getByLabel("Title", { exact: true })).toBeFocused();
  await page.getByLabel("Title", { exact: true }).fill(title);
  await page
    .getByLabel("What do you need help with?")
    .fill("Synthetic end-to-end request. No private information.");
  await page.getByLabel("What do you need help with?").press("Tab");
  await expect(
    page.getByRole("button", { name: "Submit request", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: title, exact: true }),
  ).toBeVisible();
  return { id: page.url().split("/").at(-1)!, title };
}
async function current(page: Page) {
  await page
    .getByRole("button", { name: "Refresh ticket", exact: true })
    .click();
  await expect(page.getByLabel("Action", { exact: true })).toBeVisible();
}
async function action(
  page: Page,
  operation: string,
  button: string,
  text?: string,
) {
  await page.getByLabel("Action", { exact: true }).selectOption(operation);
  if (text)
    await page
      .getByLabel(
        operation === "internal"
          ? "Internal note (staff only)"
          : operation === "reopen"
            ? "Reopening reason (public)"
            : "Public reply",
        { exact: true },
      )
      .fill(text);
  await page.getByRole("button", { name: button, exact: true }).click();
  await expect(
    page.getByText("Your update was saved.", { exact: true }),
  ).toBeVisible();
}
async function assignment(manager: Page, label = "agent-a@example.invalid") {
  await manager.getByLabel("Action", { exact: true }).selectOption("assign");
  await manager
    .getByLabel("Available agent", { exact: true })
    .selectOption({ label });
  await manager
    .getByRole("button", { name: "Change assignment", exact: true })
    .click();
  await expect(
    manager.getByText("Your update was saved.", { exact: true }),
  ).toBeVisible();
}

test("three roles complete the lifecycle with public/internal isolation and responsive keyboard forms", async ({
  page,
  browser,
}, testInfo) => {
  await login(page, "requester-a");
  const created = await create(page);
  const manager = await other(browser, page, "manager", created.id);
  await assignment(manager);
  await manager.getByLabel("Action", { exact: true }).selectOption("priority");
  await manager.getByLabel("New priority").selectOption("high");
  await manager
    .getByRole("button", { name: "Change priority", exact: true })
    .click();
  await expect(
    manager.getByText("Your update was saved.", { exact: true }),
  ).toBeVisible();
  const agent = await other(browser, page, "agent-a", created.id);
  await action(agent, "start", "Start or resume work");
  await action(
    agent,
    "internal",
    "Add internal note",
    "S12 staff-only diagnostic note.",
  );
  await action(
    agent,
    "wait",
    "Wait for customer",
    "Please verify this synthetic step.",
  );
  await action(agent, "start", "Start or resume work");
  await action(
    agent,
    "resolve",
    "Resolve ticket",
    "Synthetic resolution is ready.",
  );
  await current(page);
  await expect(
    page.getByText("S12 staff-only diagnostic note.", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Activity", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByLabel("Action", { exact: true }).locator("option"),
  ).toHaveText(["Send public reply", "Reopen ticket"]);
  await action(
    page,
    "reopen",
    "Reopen ticket",
    "The synthetic problem still occurs.",
  );
  await current(agent);
  await action(
    agent,
    "resolve",
    "Resolve ticket",
    "Verified the synthetic follow-up.",
  );
  await current(manager);
  await action(manager, "close", "Close ticket");
  await action(manager, "archive", "Archive ticket");
  await current(page);
  await expect(
    page.getByText("No actions are available for this ticket.", {
      exact: false,
    }),
  ).toBeVisible();
  await expect(page.getByLabel("Action", { exact: true })).toBeDisabled();
  await action(manager, "unarchive", "Unarchive ticket");
  await action(
    manager,
    "reopen",
    "Reopen ticket",
    "Reopen closed synthetic work.",
  );
  await current(agent);
  await expect(
    agent.getByRole("heading", { name: "Ticket unavailable", exact: true }),
  ).toBeVisible();
  await current(page);
  await expect(
    page.getByText("Awaiting assignment", { exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page
    .getByLabel("Public reply", { exact: true })
    .fill("An unsent synthetic draft for responsive verification.");
  await page.getByLabel("Public reply", { exact: true }).press("Tab");
  await expect(
    page.getByRole("button", { name: "Send public reply", exact: true }),
  ).toBeFocused();
  // Capture from the document origin so offscreen fixed controls are not composited into the middle of a full-page image.
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: testInfo.outputPath("final-ticket.png"),
    fullPage: true,
  });
});

test("concurrent assignments and replies preserve drafts until explicit version review", async ({
  page,
  browser,
}) => {
  await login(page, "requester-a");
  const created = await create(page);
  const manager = await other(browser, page, "manager", created.id);
  await manager.getByLabel("Action", { exact: true }).selectOption("assign");
  await manager
    .getByLabel("Available agent", { exact: true })
    .selectOption({ label: "agent-b@example.invalid" });
  await action(
    page,
    "public",
    "Send public reply",
    "Concurrent synthetic reply.",
  );
  await manager
    .getByRole("button", { name: "Change assignment", exact: true })
    .click();
  await expect(manager.getByRole("alert")).toContainText("Request 409");
  await expect(
    manager
      .getByLabel("Available agent", { exact: true })
      .locator("option:checked"),
  ).toHaveText("agent-b@example.invalid");
  await expect(
    manager.getByRole("button", { name: "Change assignment", exact: true }),
  ).toBeDisabled();
  await manager
    .getByRole("button", { name: "Use reviewed version 2", exact: true })
    .click();
  await manager
    .getByRole("button", { name: "Change assignment", exact: true })
    .click();
  await expect(
    manager.getByText("Your update was saved.", { exact: true }),
  ).toBeVisible();
  await current(page);
  await expect(page.getByText(/Current version: 3\./)).toBeVisible();
  await page
    .getByLabel("Public reply", { exact: true })
    .fill("My original unsent draft.");
  await expect(manager.getByText(/Current version: 3\./)).toBeVisible();
  await manager.getByLabel("Action", { exact: true }).selectOption("priority");
  await manager.getByLabel("New priority").selectOption("urgent");
  // A previous success notice can remain visible until React renders the new pending state.
  // Synchronize the competing write on its actual HTTP result, not that old notice.
  const prioritySaved = manager.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      response.url().endsWith(`/api/tickets/${created.id}`),
  );
  await manager
    .getByRole("button", { name: "Change priority", exact: true })
    .click();
  expect((await prioritySaved).status()).toBe(200);
  await expect(
    manager.getByText("Your update was saved.", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Send public reply", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Use reviewed version 4", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Public reply", { exact: true })).toHaveValue(
    "My original unsent draft.",
  );
  await page
    .getByRole("button", { name: "Use reviewed version 4", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Send public reply", exact: true })
    .click();
  await expect(
    page.getByText("Your update was saved.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("My original unsent draft.", { exact: true }),
  ).toHaveCount(1);
});

test("a lost committed creation acknowledgement and double-click reply create no duplicates", async ({
  page,
}) => {
  await login(page, "requester-a");
  const attempts: { key: string | undefined; body: string | null }[] = [];
  await page.route("**/api/tickets", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    attempts.push({
      key: route.request().headers()["idempotency-key"],
      body: route.request().postData(),
    });
    const response = await route.fetch();
    expect(response.status()).toBe(201);
    if (attempts.length === 1)
      return route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ error: { code: "test_lost_response" } }),
      });
    await route.fulfill({ response });
  });
  const title = `[S12 retry] ${randomUUID()}`;
  await page.getByRole("link", { name: "New request", exact: true }).click();
  await page.getByLabel("Title", { exact: true }).fill(title);
  await page
    .getByLabel("What do you need help with?")
    .fill("Synthetic lost acknowledgement.");
  await page
    .getByRole("button", { name: "Submit request", exact: true })
    .dblclick();
  await expect(
    page.getByRole("button", { name: "Retry same request", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Title", { exact: true })).toBeDisabled();
  expect(attempts).toHaveLength(1);
  await page
    .getByRole("button", { name: "Retry same request", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: title, exact: true }),
  ).toBeVisible();
  expect(attempts).toHaveLength(2);
  expect(attempts[1]).toEqual(attempts[0]);
  let replyCalls = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/messages"))
      replyCalls++;
  });
  await page
    .getByLabel("Public reply", { exact: true })
    .fill("One synthetic reply only.");
  await page
    .getByRole("button", { name: "Send public reply", exact: true })
    .dblclick();
  await expect(
    page.getByText("Your update was saved.", { exact: true }),
  ).toBeVisible();
  expect(replyCalls).toBe(1);
  await expect(
    page.getByText("One synthetic reply only.", { exact: true }),
  ).toHaveCount(1);
  await page
    .getByRole("link", { name: "← Back to tickets", exact: true })
    .click();
  await expect(
    page.getByRole("link", {
      name: new RegExp(title.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")),
    }),
  ).toHaveCount(1);
});

test("real object authorization, empty state, failed revalidation and session clearing", async ({
  page,
}) => {
  await login(page, "agent-b");
  // Other tests may assign agent-b their own synthetic tickets; an unmatched filter is deterministic.
  await page.getByLabel("Search requests").fill(`unmatched-${randomUUID()}`);
  await page
    .getByRole("button", { name: "Apply filters", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Nothing here yet", exact: true }),
  ).toBeVisible();
  await page.goto(`/#/tickets/${seedId}`);
  await expect(
    page.getByRole("heading", { name: "Ticket unavailable", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, "requester-b", `/tickets/${seedId}`);
  await expect(
    page.getByRole("heading", { name: "Ticket unavailable", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, "requester-a", `/tickets/${seedId}`);
  await expect(
    page.getByRole("heading", { name: "Original request", exact: true }),
  ).toBeVisible();
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(`**/api/tickets/${seedId}`, async (route) => {
    await gate;
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: '{"error":{"code":"test_failure"}}',
    });
  });
  await page
    .getByRole("button", { name: "Refresh ticket", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Loading ticket", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Original request", exact: true }),
  ).toHaveCount(0);
  release();
  await expect(page.getByRole("alert")).toContainText("Request 503");
  await expect(page.getByText(/Literal markup must remain text/)).toHaveCount(
    0,
  );
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByLabel("Email address")).toBeVisible();
  await expect(page.getByLabel("Public reply", { exact: true })).toHaveCount(0);
  expect(
    await page.evaluate(() => localStorage.length + sessionStorage.length),
  ).toBe(0);
});

test("server-backed filters reset pagination and detail return preserves the selected page", async ({
  page,
}) => {
  await login(page, "requester-a");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
  await page.getByLabel("Search requests").fill("Pagination sample");
  await page
    .getByRole("button", { name: "Apply filters", exact: true })
    .click();
  await expect(
    page.getByRole("link", { name: /Pagination sample/ }),
  ).toHaveCount(20);
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await expect(
    page.getByRole("link", { name: /Pagination sample/ }),
  ).toHaveCount(4);
  const selected = page
    .getByRole("link", { name: /Pagination sample/ })
    .first();
  await selected.click();
  await expect(
    page.getByRole("heading", { name: "Original request", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "← Back to tickets", exact: true })
    .click();
  await expect(
    page.getByRole("link", { name: /Pagination sample/ }),
  ).toHaveCount(4);
  await page.getByLabel("Priority", { exact: true }).selectOption("high");
  await page.getByLabel("Status", { exact: true }).selectOption("open");
  await page
    .getByRole("button", { name: "Apply filters", exact: true })
    .click();
  await expect(
    page.getByRole("link", { name: /Pagination sample/ }),
  ).toHaveCount(12);
  await expect(
    page.getByRole("button", { name: "Previous", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Next", exact: true }),
  ).toBeDisabled();
  await expect(page).toHaveURL(/priority=high/);
});

test("review panel displays sources and prevents evidence-free sending", async ({ page }, testInfo) => {
  const jobId = "99999999-9999-4999-8999-999999999999";
  await page.route(`**/api/tickets/${seedId}/analysis-jobs`, async (route) => {
    await route.fulfill({ json: [{ job_id: jobId, status: "succeeded", attempts: 1, error_code: null, review_decision: null }] });
  });
  await page.route(`**/api/analysis-jobs/${jobId}/suggestion`, async (route) => {
    await route.fulfill({ json: { job_id: jobId, ticket_version: 1, review_decision: null, suggestion: {
      category: "access", suggested_priority: "normal", reply_draft: "A support agent will review your request.",
      citations: [], human_verification: ["Confirm account ownership before taking action."]
    } } });
  });
  await login(page, "manager", `/tickets/${seedId}`);
  const panel = page.getByRole("region", { name: "Suggested response" });
  await expect(panel.getByText("Human follow-up needed")).toBeVisible();
  await expect(panel.getByRole("button", { name: "Approve and send" })).toBeDisabled();
  await expect(panel.getByRole("button", { name: "Reject suggestion" })).toBeEnabled();
  await panel.screenshot({ path: testInfo.outputPath("analysis-panel.png") });
});
