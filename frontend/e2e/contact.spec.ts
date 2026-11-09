import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";

const password = "S09-local-synthetic-only!";
async function signIn(page: import("@playwright/test").Page, email: string, hash: string) {
  await page.goto(`/#${hash}`);
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}

test("contact details follow ticket access", async ({ page, browser }) => {
  await signIn(page, "requester-a@example.invalid", "/tickets/new");
  const title = `Contact example ${randomUUID()}`;
  await page.getByLabel("Title", { exact: true }).fill(title);
  await page.getByLabel("What do you need help with?").fill("Synthetic contact test.");
  await page.getByLabel("Contact phone (optional)").fill("+61 400 123 456");
  await page.getByRole("button", { name: "Submit request" }).click();
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await expect(page.getByText("+61 400 123 456")).toBeVisible();
  const ticketId = page.url().split("/").at(-1)!;
  const context = await browser.newContext({ baseURL: "http://127.0.0.1:5174", viewport: page.viewportSize()! });
  try {
    const manager = await context.newPage();
    await signIn(manager, "manager@example.invalid", `/tickets/${ticketId}`);
    await expect(manager.getByText("+61 400 123 456")).toBeVisible();
    await expect(manager.getByText("requester-a@example.invalid")).toBeVisible();
  } finally {
    await context.close();
  }
});
