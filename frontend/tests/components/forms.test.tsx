import { afterEach, describe, expect, it, vi } from "vitest";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { api, ApiError } from "../../src/api/client.ts";
import { createSessionClient } from "../../src/state/queries.ts";
import { CreateTicketPage } from "../../src/pages/CreateTicketPage.tsx";
import { TicketDetailPage } from "../../src/pages/TicketDetailPage.tsx";
import { LoginPage } from "../../src/pages/LoginPage.tsx";
import { App } from "../../src/App.tsx";
import type { Session } from "../../src/App.tsx";
import type { TicketDetail } from "../../src/api/contracts.ts";

const id = "11111111-1111-4111-8111-111111111111";
const agentId = "22222222-2222-4222-8222-222222222222";
const session: Session = {
  key: "synthetic-session",
  token: "synthetic-token",
  user: { id, email: "requester@example.invalid", role: "requester" },
  expiresAt: Date.now() + 900000,
};
const ticket: TicketDetail = {
  id,
  requester_id: id,
  assignee_id: agentId,
  title: "Synthetic request",
  body: "Synthetic original body",
  status: "in_progress",
  priority: "normal",
  version: 4,
  archived: false,
  created_at: "2026-10-27T00:00:00Z",
  updated_at: "2026-10-27T00:00:00Z",
  messages: [],
};
const clients: ReturnType<typeof createSessionClient>[] = [];
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear());
});
function mount(element: React.ReactNode, expired = vi.fn()) {
  const client = createSessionClient(expired);
  clients.push(client);
  client.setDefaultOptions({
    ...client.getDefaultOptions(),
    queries: { ...client.getDefaultOptions().queries, gcTime: Infinity },
  });
  return {
    ...render(
      <QueryClientProvider client={client}>{element}</QueryClientProvider>,
    ),
    client,
  };
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
async function fillCreation() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Title"), "Synthetic title");
  await user.type(
    screen.getByLabelText("What do you need help with?"),
    "Synthetic body",
  );
  return user;
}
function detail(value: Session = session) {
  return <TicketDetailPage id={id} session={value} backHref="#/tickets" />;
}

describe("create form", () => {
  it("associates required fields, focuses the title and does not submit blank native fields", async () => {
    const send = vi.spyOn(api, "createTicket");
    mount(<CreateTicketPage session={session} backHref="#/tickets" />);
    expect(screen.getByLabelText("Title")).toHaveFocus();
    expect(screen.getByLabelText("Title")).toBeRequired();
    expect(
      screen.getByLabelText("What do you need help with?"),
    ).toHaveAttribute("aria-describedby", "create-help");
    await userEvent.click(
      screen.getByRole("button", { name: "Submit request" }),
    );
    expect(send).not.toHaveBeenCalled();
  });
  it("rejects whitespace locally and announces the error", async () => {
    const send = vi.spyOn(api, "createTicket");
    mount(<CreateTicketPage session={session} backHref="#/tickets" />);
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "   " },
    });
    fireEvent.change(screen.getByLabelText("What do you need help with?"), {
      target: { value: "Body" },
    });
    fireEvent.submit(screen.getByRole("form", { name: "New support request" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Enter a title and description",
    );
    expect(send).not.toHaveBeenCalled();
  });
  it("guards repeated submissions synchronously while a request is pending", async () => {
    const response = deferred<typeof ticket>();
    const send = vi
      .spyOn(api, "createTicket")
      .mockReturnValue(response.promise);
    mount(<CreateTicketPage session={session} backHref="#/tickets" />);
    await fillCreation();
    const form = screen.getByRole("form", { name: "New support request" });
    fireEvent.submit(form);
    fireEvent.submit(form);
    await waitFor(() => expect(send).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("button", { name: "Submitting…" })).toBeDisabled();
    await act(async () => response.resolve(ticket));
    await waitFor(() => expect(window.location.hash).toBe(`#/tickets/${id}`));
  });
  it("locks uncertain input and retries the exact creation body/key", async () => {
    const send = vi
      .spyOn(api, "createTicket")
      .mockRejectedValueOnce(new ApiError(503, "unavailable", "Please retry"))
      .mockResolvedValue(ticket);
    mount(<CreateTicketPage session={session} backHref="#/tickets" />);
    const user = await fillCreation();
    await user.click(screen.getByRole("button", { name: "Submit request" }));
    await screen.findByRole("button", { name: "Retry same request" });
    expect(screen.getByLabelText("Title")).toBeDisabled();
    expect(screen.getByLabelText("Title")).toHaveValue("Synthetic title");
    await user.click(
      screen.getByRole("button", { name: "Retry same request" }),
    );
    await waitFor(() => expect(send).toHaveBeenCalledTimes(2));
    expect(send.mock.calls[1].slice(0, 3)).toEqual(
      send.mock.calls[0].slice(0, 3),
    );
  });
  it("aborts on unmount and ignores a late successful write without navigation", async () => {
    const response = deferred<typeof ticket>();
    const send = vi
      .spyOn(api, "createTicket")
      .mockReturnValue(response.promise);
    const view = mount(
      <CreateTicketPage session={session} backHref="#/tickets" />,
    );
    const user = await fillCreation();
    await user.click(screen.getByRole("button", { name: "Submit request" }));
    const signal = send.mock.calls[0][3]!;
    view.unmount();
    expect(signal.aborted).toBe(true);
    await act(async () => response.resolve(ticket));
    expect(window.location.hash).not.toContain(id);
  });
});

describe("ticket actions", () => {
  it("preserves text through409/refetch and requires explicit reviewed version before a new submission", async () => {
    vi.spyOn(api, "ticket")
      .mockResolvedValueOnce(ticket)
      .mockResolvedValue({ ...ticket, version: 5 });
    const send = vi
      .spyOn(api, "message")
      .mockRejectedValueOnce(
        new ApiError(409, "version_conflict", "Reload current data"),
      )
      .mockResolvedValue({
        ticket_version: 6,
        message: {
          id,
          author_id: id,
          body: "Retained draft",
          visibility: "public",
          created_at: ticket.created_at,
        },
      });
    mount(detail());
    const user = userEvent.setup();
    await user.type(
      await screen.findByLabelText("Public reply"),
      "Retained draft",
    );
    await user.click(screen.getByRole("button", { name: "Send public reply" }));
    const review = await screen.findByRole("button", {
      name: "Use reviewed version 5",
    });
    expect(screen.getByLabelText("Public reply")).toHaveValue("Retained draft");
    expect(
      screen.getByRole("button", { name: "Send public reply" }),
    ).toBeDisabled();
    expect(send).toHaveBeenCalledTimes(1);
    await user.click(review);
    expect(send).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole("button", { name: "Send public reply" }));
    await waitFor(() => expect(send).toHaveBeenCalledTimes(2));
    expect(send.mock.calls[0][2].expected_version).toBe(4);
    expect(send.mock.calls[1][2]).toMatchObject({
      expected_version: 5,
      body: "Retained draft",
    });
    expect(send.mock.calls[0][3]).not.toBe(send.mock.calls[1][3]);
  });
  it("retries the submitted resolution after an uncertain response even when refreshed status is resolved", async () => {
    vi.spyOn(api, "ticket")
      .mockResolvedValueOnce(ticket)
      .mockResolvedValue({ ...ticket, version: 5, status: "resolved" });
    const send = vi
      .spyOn(api, "patchTicket")
      .mockRejectedValueOnce(new ApiError(0, "timeout", "Timed out"))
      .mockResolvedValue({ ...ticket, version: 5, status: "resolved" });
    mount(detail({ ...session, user: { ...session.user, role: "agent" } }));
    const user = userEvent.setup();
    await user.selectOptions(await screen.findByLabelText("Action"), "resolve");
    await user.type(
      screen.getByLabelText("Public reply"),
      "Synthetic resolution",
    );
    await user.click(screen.getByRole("button", { name: "Resolve ticket" }));
    await screen.findByRole("button", { name: "Retry same request" });
    await user.click(screen.getByRole("button", { name: "Refresh ticket" }));
    await screen.findByRole("button", { name: "Retry same request" });
    expect(screen.getByText(/Current version: 5/)).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Retry same request" }),
    );
    await waitFor(() => expect(send).toHaveBeenCalledTimes(2));
    expect(send.mock.calls[1].slice(0, 4)).toEqual(
      send.mock.calls[0].slice(0, 4),
    );
    expect(send.mock.calls[1][2]).toEqual({
      expected_version: 4,
      status: "resolved",
      public_reply: "Synthetic resolution",
    });
  });
  it("retains an unavailable selected agent after directory refresh and disables saving", async () => {
    vi.spyOn(api, "ticket").mockResolvedValue(ticket);
    vi.spyOn(api, "agents")
      .mockResolvedValueOnce([
        { id: agentId, email: "agent@example.invalid", role: "agent" },
      ])
      .mockResolvedValue([]);
    mount(detail({ ...session, user: { ...session.user, role: "manager" } }));
    const user = userEvent.setup();
    await user.selectOptions(await screen.findByLabelText("Action"), "assign");
    await screen.findByRole("option", { name: "agent@example.invalid" });
    await user.selectOptions(screen.getByLabelText("Available agent"), agentId);
    await user.click(screen.getByRole("button", { name: "Refresh agents" }));
    expect(
      await screen.findByRole("option", { name: /Selected agent unavailable/ }),
    ).toBeDisabled();
    expect(screen.getByLabelText("Available agent")).toHaveValue(agentId);
    expect(
      screen.getByRole("button", { name: "Change assignment" }),
    ).toBeDisabled();
  });
  it("expires on mutation401 and does not automatically retry", async () => {
    vi.spyOn(api, "ticket").mockResolvedValue(ticket);
    const send = vi
      .spyOn(api, "message")
      .mockRejectedValue(new ApiError(401, "invalid_session", "Sign in again"));
    const expired = vi.fn();
    mount(detail(), expired);
    const user = userEvent.setup();
    await user.type(
      await screen.findByLabelText("Public reply"),
      "Synthetic reply",
    );
    await user.click(screen.getByRole("button", { name: "Send public reply" }));
    await waitFor(() => expect(expired).toHaveBeenCalledTimes(1));
    expect(send).toHaveBeenCalledTimes(1);
  });
  it("shows loading/error states and removes old private detail when revalidation fails", async () => {
    const response = deferred<TicketDetail>();
    vi.spyOn(api, "ticket")
      .mockReturnValueOnce(response.promise)
      .mockRejectedValue(new ApiError(404, "not_found", "Unavailable"));
    mount(detail());
    expect(screen.getByRole("status")).toHaveTextContent("Loading ticket");
    await act(async () => response.resolve(ticket));
    await screen.findByRole("heading", { name: ticket.title });
    await userEvent.click(
      screen.getByRole("button", { name: "Refresh ticket" }),
    );
    await screen.findByRole("alert");
    expect(screen.queryByText(ticket.body)).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Public reply")).not.toBeInTheDocument();
  });
});

it("clears a failed sign-in password and announces the safe authentication error", async () => {
  vi.spyOn(api, "login").mockRejectedValue(
    new ApiError(401, "invalid_credentials", "Incorrect email or password."),
  );
  render(<LoginPage notice="" onSignIn={vi.fn()} />);
  const user = userEvent.setup();
  await user.type(
    screen.getByLabelText("Email address"),
    "synthetic@example.invalid",
  );
  await user.type(screen.getByLabelText("Password"), "synthetic-password");
  await user.click(screen.getByRole("button", { name: /Sign in/ }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Incorrect email or password.",
  );
  expect(screen.getByLabelText("Password")).toHaveValue("");
});

it("logout aborts a pending read and a late old-account response cannot enter the new workspace", async () => {
  const old = deferred<{ items: (typeof ticket)[]; next_cursor: null }>();
  vi.spyOn(api, "login").mockResolvedValue({
    access_token: "synthetic-token",
    token_type: "bearer",
    expires_in: 900,
  });
  vi.spyOn(api, "me")
    .mockResolvedValueOnce(session.user)
    .mockResolvedValue({
      ...session.user,
      id: agentId,
      email: "agent@example.invalid",
      role: "agent",
    });
  const reads = vi
    .spyOn(api, "tickets")
    .mockReturnValueOnce(old.promise)
    .mockResolvedValue({ items: [], next_cursor: null });
  render(<App />);
  const user = userEvent.setup();
  async function signIn() {
    await user.type(
      screen.getByLabelText("Email address"),
      "synthetic@example.invalid",
    );
    await user.type(screen.getByLabelText("Password"), "synthetic-password");
    await user.click(screen.getByRole("button", { name: /Sign in/ }));
  }
  await signIn();
  await screen.findByRole("heading", { name: "Loading tickets" });
  const signal = reads.mock.calls[0][2]!;
  await user.click(screen.getByRole("button", { name: /Sign out/ }));
  expect(signal.aborted).toBe(true);
  await signIn();
  await screen.findByRole("heading", { name: "Nothing here yet" });
  await act(async () =>
    old.resolve({
      items: [{ ...ticket, title: "Old requester private title" }],
      next_cursor: null,
    }),
  );
  expect(
    screen.queryByText("Old requester private title"),
  ).not.toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Assigned to you" }),
  ).toBeInTheDocument();
});
