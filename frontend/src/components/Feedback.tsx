import { ApiError } from "../api/client.ts";

export function Loading({
  label = "Loading your workspace",
}: {
  label?: string;
}) {
  return (
    <div className="feedback" role="status">
      <span className="spinner" aria-hidden="true" />
      <h2>{label}</h2>
      <p>This should only take a moment.</p>
    </div>
  );
}
export function ErrorPanel({
  error,
  retry,
}: {
  error: ApiError;
  retry?: () => void;
}) {
  const title =
    error.status === 403
      ? "Access restricted"
      : error.status === 404
        ? "Ticket unavailable"
        : error.status === 409
          ? "A newer version is available"
          : "We could not complete that request";
  return (
    <section className="error-panel" role="alert">
      <p className="eyebrow">
        {error.status ? `Request ${error.status}` : "Connection issue"}
      </p>
      <h2>{title}</h2>
      <p>{error.message}</p>
      {error.retryAfter && <p>Try again in {error.retryAfter} seconds.</p>}
      {error.requestId && (
        <p className="request-id">
          Request ID: <code>{error.requestId}</code>
        </p>
      )}
      <div className="actions">
        {retry && (
          <button className="button secondary" onClick={retry}>
            Try again
          </button>
        )}
        {error.status === 404 || error.status === 403 ? (
          <a className="button secondary" href="#/tickets">
            Back to tickets
          </a>
        ) : null}
      </div>
    </section>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="feedback empty">
      <span className="empty-mark" aria-hidden="true">
        —
      </span>
      <h2>{title}</h2>
      <p>{children}</p>
    </div>
  );
}
