import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { api, ApiError } from "../api/client.ts";
import type { Session } from "../App.tsx";
import { ErrorPanel } from "../components/Feedback.tsx";

export function LoginPage({
  notice,
  onSignIn,
}: {
  notice: string;
  onSignIn: (session: Session) => void;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const request = useRef<AbortController | null>(null);
  const formRef = useRef<HTMLFormElement>(null);
  useEffect(() => () => request.current?.abort(), []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setPending(true);
    setError(null);
    const data = new FormData(event.currentTarget);
    const startedAt = Date.now();
    try {
      const token = await api.login(
        String(data.get("email")),
        String(data.get("password")),
        controller.signal,
      );
      const user = await api.me(token.access_token, controller.signal);
      if (!controller.signal.aborted)
        onSignIn({
          key: crypto.randomUUID(),
          token: token.access_token,
          user,
          expiresAt: startedAt + token.expires_in * 1000,
        });
    } catch (failure) {
      if (!controller.signal.aborted)
        setError(
          failure instanceof ApiError
            ? failure
            : new ApiError(
                0,
                "unexpected_error",
                "Unable to sign in. Please try again.",
              ),
        );
    } finally {
      const password = formRef.current?.elements.namedItem("password");
      if (password instanceof HTMLInputElement) password.value = "";
      if (request.current === controller) request.current = null;
      if (!controller.signal.aborted) setPending(false);
    }
  }
  return (
    <main className="login-layout">
      <section className="login-story">
        <a className="brand" href="#/tickets">
          <span className="brand-mark" aria-hidden="true">
            S
          </span>
          SupportOps<span className="brand-ai">AI</span>
        </a>
        <div>
          <p className="eyebrow">A little more clarity. Every day.</p>
          <h1>
            Good support
            <br />
            starts with context.
          </h1>
          <p className="story-copy">
            One place for the conversation, the responsibility, and the next
            step.
          </p>
          <div className="story-lines">
            <p>
              <span>01</span> Keep every request in view.
            </p>
            <p>
              <span>02</span> Give every handoff a history.
            </p>
            <p>
              <span>03</span> Make progress easy to follow.
            </p>
          </div>
        </div>
        <p className="demo-label">
          <span aria-hidden="true" />
          Synthetic demonstration workspace
        </p>
      </section>
      <section className="login-panel" aria-labelledby="login-heading">
        <div className="login-form-wrap">
          <p className="eyebrow">Your support workspace</p>
          <h2 id="login-heading">Welcome back.</h2>
          <p className="muted">Sign in to see the tickets available to you.</p>
          {notice && (
            <p className="notice" role="status">
              {notice}
            </p>
          )}
          <form ref={formRef} onSubmit={submit} aria-busy={pending}>
            <label htmlFor="email">Email address</label>
            <input
              id="email"
              name="email"
              type="email"
              required
              maxLength={254}
              autoComplete="username"
              placeholder="you@example.com"
              disabled={pending}
            />
            <label htmlFor="password">Password</label>
            <input
              id="password"
              name="password"
              type="password"
              required
              minLength={1}
              maxLength={128}
              autoComplete="current-password"
              disabled={pending}
              aria-describedby="session-hint"
            />
            <button
              className="button primary login-submit"
              disabled={pending}
              type="submit"
            >
              {pending ? "Signing in…" : "Sign in"}
              <span aria-hidden="true">→</span>
            </button>
          </form>
          {pending && (
            <p role="status" className="muted">
              Checking your account…
            </p>
          )}
          {error && <ErrorPanel error={error} />}
          <p id="session-hint" className="session-hint">
            Use your assigned account. Sessions end when you refresh or close
            this page.
          </p>
        </div>
        <p className="login-footer">Human judgment. Clear accountability.</p>
      </section>
    </main>
  );
}
