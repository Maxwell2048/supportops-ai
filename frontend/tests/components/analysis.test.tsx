import { afterEach, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { api, ApiError } from "../../src/api/client.ts";
import { AnalysisPanel } from "../../src/components/AnalysisPanel.tsx";
import { createSessionClient } from "../../src/state/queries.ts";
import type { TicketDetail } from "../../src/api/contracts.ts";
import type { Session } from "../../src/App.tsx";

const id = "11111111-1111-4111-8111-111111111111";
const session: Session = { key: "review-test", token: "test", expiresAt: Date.now() + 100000, user: { id, email: "agent@example.invalid", role: "agent" } };
const ticket: TicketDetail = { id, requester_id: id, assignee_id: id, title: "Test", body: "Synthetic", status: "in_progress", priority: "normal", version: 1, archived: false, created_at: "2026-11-09T00:00:00Z", updated_at: "2026-11-09T00:00:00Z", messages: [] };
const job = { job_id: id, status: "succeeded" as const, attempts: 1, error_code: null, review_decision: null };
const makeSuggestion = (evidence: boolean) => ({ job_id: id, ticket_version: 1, review_decision: null, suggestion: { category: "other" as const, suggested_priority: "normal" as const, reply_draft: "Draft response", citations: evidence ? [{ chunk_id: id, version_id: id, quote: "A real source." }] : [], human_verification: ["Check account"] } });
const clients: ReturnType<typeof createSessionClient>[] = [];
afterEach(() => { vi.restoreAllMocks(); clients.splice(0).forEach((client) => client.clear()); });
function mount() {
  const client = createSessionClient(vi.fn());
  clients.push(client);
  render(<QueryClientProvider client={client}><AnalysisPanel ticket={ticket} session={session} /></QueryClientProvider>);
}

it("prevents sending a suggestion without evidence", async () => {
  vi.spyOn(api, "analysisJobs").mockResolvedValue([job]);
  vi.spyOn(api, "suggestion").mockResolvedValue(makeSuggestion(false));
  mount();
  expect(await screen.findByText("Human follow-up needed")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Approve and send" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Send edited reply" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Reject suggestion" })).toBeEnabled();
});

it("preserves the review request and key after uncertain network failure", async () => {
  vi.spyOn(api, "analysisJobs").mockResolvedValue([job]);
  vi.spyOn(api, "suggestion").mockResolvedValue(makeSuggestion(true));
  const send = vi.spyOn(api, "reviewSuggestion").mockRejectedValueOnce(new ApiError(0, "timeout", "Timed out"))
    .mockResolvedValueOnce({ job_id: id, decision: "accepted", message_id: id, ticket_version: 2 });
  mount();
  await screen.findByText("A real source.");
  await userEvent.click(screen.getByRole("button", { name: "Approve and send" }));
  const retry = await screen.findByRole("button", { name: "Retry previous request" });
  expect(screen.getByLabelText("Response draft")).toBeDisabled();
  await userEvent.click(retry);
  await waitFor(() => expect(send).toHaveBeenCalledTimes(2));
  expect(send.mock.calls[0][2]).toEqual(send.mock.calls[1][2]);
  expect(send.mock.calls[0][3]).toBe(send.mock.calls[1][3]);
});
