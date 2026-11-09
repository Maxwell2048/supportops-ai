import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../api/client.ts";
import type { Session } from "../App.tsx";
import type { TicketDetail } from "../api/contracts.ts";
import { invalidateTickets } from "../state/queries.ts";
import { ErrorPanel } from "./Feedback.tsx";

type Decision = "accepted" | "edited" | "rejected";
type Pending = { kind: "create"; key: string; version: number } | {
  kind: "review"; key: string; jobId: string;
  body: { expected_version: number; decision: Decision; edited_body?: string };
};

export function AnalysisPanel({ ticket, session }: { ticket: TicketDetail; session: Session }) {
  const client = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const lock = useRef(false);
  const pending = useRef<Pending | null>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  const list = useQuery({
    queryKey: ["analysis", session.key, ticket.id],
    queryFn: ({ signal }) => api.analysisJobs(ticket.id, session.token, signal),
    refetchInterval: (query) => query.state.data?.some((job) => job.status === "queued" || job.status === "running") ? 3000 : false,
    retry: false,
  });
  const selectedJob = list.data?.find((job) => job.job_id === selected) ?? list.data?.[0];
  const suggestion = useQuery({
    queryKey: ["suggestion", session.key, selectedJob?.job_id],
    queryFn: ({ signal }) => api.suggestion(selectedJob!.job_id, session.token, signal),
    enabled: selectedJob?.status === "succeeded",
    retry: false,
  });
  const mutation = useMutation({
    retry: false,
    mutationFn: async ({ attempt, signal }: { attempt: Pending; signal: AbortSignal }): Promise<{ job_id: string }> =>
      attempt.kind === "create"
        ? api.createAnalysis(ticket.id, session.token, attempt.version, attempt.key, signal)
        : api.reviewSuggestion(attempt.jobId, session.token, attempt.body, attempt.key, signal),
  });
  useEffect(() => {
    setDraft(suggestion.data?.suggestion.reply_draft ?? "");
  }, [suggestion.data?.job_id]);

  async function submit(attempt: Pending) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError(null);
    setNotice("");
    pending.current = attempt;
    controller.current = new AbortController();
    try {
      const result = await mutation.mutateAsync({ attempt, signal: controller.current.signal });
      if (attempt.kind === "create") {
        setSelected(result.job_id);
        setNotice("Analysis queued. A worker will process this request.");
      } else {
        setNotice(attempt.body.decision === "rejected" ? "Suggestion rejected. No reply was sent." : "Your reviewed reply was sent.");
        await invalidateTickets(client, session);
        await client.invalidateQueries({ queryKey: ["suggestion", session.key, attempt.jobId] });
      }
      setUncertain(false);
      pending.current = null;
      await list.refetch();
    } catch (failure) {
      if (controller.current?.signal.aborted) return;
      const safe = failure instanceof ApiError ? failure : new ApiError(0, "network_error", "Unable to reach the service.");
      setError(safe);
      const ambiguous = safe.status === 0 || safe.status >= 500 || safe.code === "invalid_response";
      setUncertain(ambiguous);
      if (!ambiguous) pending.current = null;
      if ([403, 404, 409].includes(safe.status)) await invalidateTickets(client, session);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  function decide(decision: Decision) {
    if (!suggestion.data || busy || uncertain) return;
    const body: Extract<Pending, { kind: "review" }>["body"] = {
      expected_version: suggestion.data.ticket_version,
      decision,
      ...(decision === "edited" ? { edited_body: draft.trim() } : {}),
    };
    void submit({ kind: "review", key: crypto.randomUUID(), jobId: suggestion.data.job_id, body });
  }

  return <section className="panel analysis-panel" aria-labelledby="analysis-heading">
    <div className="analysis-header">
      <div><p className="eyebrow">Support intelligence</p><h2 id="analysis-heading">Suggested response</h2>
        <p className="muted small">Review the evidence and response before anything is sent.</p></div>
      <span className="analysis-badge">Human review</span>
    </div>
    <div className="analysis-content">
      {notice && <p role="status" className="analysis-notice">{notice}</p>}
      {error && <ErrorPanel error={error} />}
      {uncertain && <div className="analysis-alert"><p>The previous request may have completed. Retry the same request to confirm its result.</p><button className="button secondary" disabled={busy} onClick={() => pending.current && void submit(pending.current)}>Retry previous request</button></div>}
      {list.isLoading && <p role="status">Loading analysis history…</p>}
      {list.isError && <ErrorPanel error={list.error as ApiError} retry={() => void list.refetch()} />}
      {list.data && !list.isError && !list.isFetching && <>
        <div className="analysis-toolbar">
          <label htmlFor="analysis-history">Analysis history</label>
          {list.data.length > 0 && <select id="analysis-history" value={selectedJob?.job_id ?? ""} disabled={busy || uncertain} onChange={(event) => { setSelected(event.target.value); setError(null); setNotice(""); }}>
            {list.data.map((job, index) => <option key={job.job_id} value={job.job_id}>{index === 0 ? "Latest" : `Earlier ${index}`} · {job.status}{job.review_decision ? ` · ${job.review_decision}` : ""}</option>)}
          </select>}
          <button className="button secondary" disabled={busy || uncertain || ticket.archived || ticket.status === "closed"} onClick={() => void submit({ kind: "create", key: crypto.randomUUID(), version: ticket.version })}>Run analysis</button>
        </div>
        {!selectedJob && <p className="muted">No analysis yet. Run an analysis to prepare a draft for review.</p>}
        {selectedJob && selectedJob.status !== "succeeded" && <div className="analysis-status" role="status"><strong>{selectedJob.status === "failed" ? "Analysis could not be completed" : "Analysis in progress"}</strong><p>{selectedJob.status === "failed" ? `Reason: ${selectedJob.error_code ?? "unavailable"}. Run a new analysis after resolving the issue.` : "This panel updates while the worker processes the request."}</p></div>}
        {suggestion.isLoading && selectedJob?.status === "succeeded" && <p role="status">Loading suggestion…</p>}
        {suggestion.isError && selectedJob?.status === "succeeded" && <ErrorPanel error={suggestion.error as ApiError} retry={() => void suggestion.refetch()} />}
        {suggestion.data && !suggestion.isError && !suggestion.isFetching && selectedJob?.status === "succeeded" && <div className="analysis-result">
          <div className="analysis-result-meta"><span>Category · {suggestion.data.suggestion.category.replaceAll("_", " ")}</span><span>Suggested priority · {suggestion.data.suggestion.suggested_priority}</span></div>
          {suggestion.data.suggestion.citations.length > 0 ? <div className="analysis-evidence"><h3>Source evidence</h3>{suggestion.data.suggestion.citations.map((citation, index) => <blockquote key={`${citation.chunk_id}-${index}`}><p>{citation.quote}</p><small>Source {citation.version_id.slice(0, 8)} · passage {citation.chunk_id.slice(0, 8)}</small></blockquote>)}</div> : <div className="analysis-alert"><strong>Human follow-up needed</strong><p>No matching evidence was found. Reject this suggestion and write your own reply.</p></div>}
          {suggestion.data.suggestion.human_verification.length > 0 && <div className="analysis-checks"><h3>Check before responding</h3><ul>{suggestion.data.suggestion.human_verification.map((item, index) => <li key={index}>{item}</li>)}</ul></div>}
          <label htmlFor="analysis-draft">Response draft</label>
          <textarea id="analysis-draft" rows={5} maxLength={10000} value={draft} disabled={busy || uncertain || !!suggestion.data.review_decision} onChange={(event) => setDraft(event.target.value)} />
          {suggestion.data.review_decision ? <p className="analysis-notice">Reviewed · {suggestion.data.review_decision}</p> : <div className="analysis-actions">
            <button className="button primary" disabled={busy || uncertain || !suggestion.data.suggestion.citations.length || draft !== suggestion.data.suggestion.reply_draft} onClick={() => decide("accepted")}>Approve and send</button>
            <button className="button secondary" disabled={busy || uncertain || !suggestion.data.suggestion.citations.length || !draft.trim()} onClick={() => decide("edited")}>Send edited reply</button>
            <button className="button secondary" disabled={busy || uncertain} onClick={() => decide("rejected")}>Reject suggestion</button>
          </div>}
          <p className="small muted">A source quote confirms its origin. Check that it supports your response.</p>
        </div>}
      </>}
    </div>
  </section>;
}
