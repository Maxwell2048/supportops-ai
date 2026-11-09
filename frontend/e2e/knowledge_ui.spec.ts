import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";

const password = "S09-local-synthetic-only!";

async function signIn(page: import("@playwright/test").Page, role: string) {
  await page.goto("/#/knowledge");
  await page.getByLabel("Email address").fill(`${role}@example.invalid`);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}

test("manager creates, indexes, publishes and archives a source", async ({ page }, testInfo) => {
  await signIn(page, "manager");
  await expect(page.getByRole("heading", { name: "Knowledge library" })).toBeVisible();
  await page.getByRole("button", { name: "New article" }).click();
  const title = `Synthetic knowledge ${randomUUID()}`;
  await page.getByLabel("Title", { exact: true }).fill(title);
  await page.getByLabel("Article content").fill("Synthetic instructions for the support team.");
  await page.getByLabel("Source reference").fill("synthetic/ui-test");
  await page.getByLabel("License note").fill("Synthetic test data");
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Draft saved. Index it before publishing.")).toBeVisible();
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("knowledge-library.png"), fullPage: true });
  await page.getByRole("button", { name: "Index this version" }).click();
  await expect(page.getByText("Keyword index is ready for this version.")).toBeVisible();
  await page.getByRole("button", { name: "Publish this version" }).click();
  await expect(page.getByText("Version published.")).toBeVisible();
  await page.getByRole("button", { name: "Archive publication" }).click();
  await expect(page.getByText("Publication archived.")).toBeVisible();
});

test("requesters cannot open the management workspace", async ({ page }) => {
  await signIn(page, "requester-a");
  await expect(page.getByRole("heading", { name: "Access restricted" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Knowledge" })).toHaveCount(0);
});
