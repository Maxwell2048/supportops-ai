import { afterEach, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { api, ApiError } from "../../src/api/client.ts";
import { KnowledgePage } from "../../src/pages/KnowledgePage.tsx";
import { createSessionClient } from "../../src/state/queries.ts";
import type { Session } from "../../src/App.tsx";

const id = "11111111-1111-4111-8111-111111111111";
const session: Session = { key: "knowledge-test", token: "test", expiresAt: Date.now() + 100000, user: { id, email: "manager@example.invalid", role: "manager" } };
const article = { id, revision: 1, published_version_id: null, archived: false, version: { id, title: "Synthetic title", body: "Synthetic text", number: 1, scope: "support" as const, source_kind: "synthetic" as const, source_reference: "synthetic", license_note: "synthetic", status: "draft" as const } };
const clients: ReturnType<typeof createSessionClient>[] = [];
afterEach(() => { vi.restoreAllMocks(); clients.splice(0).forEach((client) => client.clear()); });
function mount(user = session) {
  const client = createSessionClient(vi.fn());
  clients.push(client);
  render(<QueryClientProvider client={client}><KnowledgePage session={user} /></QueryClientProvider>);
}

it("retains the exact draft and key after an uncertain save", async () => {
  vi.spyOn(api, "knowledgeArticles").mockResolvedValue({ items: [], next_cursor: null });
  vi.spyOn(api, "knowledgeArticle").mockResolvedValue(article);
  const save = vi.spyOn(api, "saveKnowledge").mockRejectedValueOnce(new ApiError(0, "timeout", "Timed out")).mockResolvedValueOnce(article);
  mount();
  await userEvent.click(await screen.findByRole("button", { name: "New article" }));
  await userEvent.type(screen.getByLabelText("Title"), "Synthetic title");
  await userEvent.type(screen.getByLabelText("Article content"), "Synthetic text");
  await userEvent.type(screen.getByLabelText("Source reference"), "synthetic");
  await userEvent.type(screen.getByLabelText("License note"), "synthetic");
  await userEvent.click(screen.getByRole("button", { name: "Save draft" }));
  expect(await screen.findByRole("button", { name: "Retry previous request" })).toBeEnabled();
  expect(screen.getByLabelText("Title")).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Retry previous request" }));
  await waitFor(() => expect(save).toHaveBeenCalledTimes(2));
  expect(save.mock.calls[0][1]).toEqual(save.mock.calls[1][1]);
  expect(save.mock.calls[0][2]).toBe(save.mock.calls[1][2]);
});

it("does not request knowledge for requesters", () => {
  const list = vi.spyOn(api, "knowledgeArticles");
  mount({ ...session, user: { ...session.user, role: "requester" } });
  expect(screen.getByRole("heading", { name: "Access restricted" })).toBeInTheDocument();
  expect(list).not.toHaveBeenCalled();
});
