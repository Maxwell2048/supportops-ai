import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Session } from "../App.tsx";
import { api, ApiError } from "../api/client.ts";
import type { KnowledgeDraft } from "../api/contracts.ts";
import { ErrorPanel } from "../components/Feedback.tsx";

type Attempt = { kind: "save"; key: string; body: KnowledgeDraft } | {
  kind: "index" | "publish" | "archive"; key: string; id: string; version: string; revision: number;
};
const emptyDraft: KnowledgeDraft = { title: "", body: "", scope: "support", source_kind: "synthetic", source_reference: "", license_note: "" };

export function KnowledgePage({ session }: { session: Session }) {
  const client = useQueryClient();
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const [selected, setSelected] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<KnowledgeDraft>(emptyDraft);
  const [error, setError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState("");
  const [uncertain, setUncertain] = useState(false);
  const [busy, setBusy] = useState(false);
  const pending = useRef<Attempt | null>(null);
  const locked = useRef(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  const manager = session.user.role === "manager";
  const list = useQuery({ queryKey: ["knowledge", session.key, "list", cursors[cursors.length - 1]],
    queryFn: ({ signal }) => api.knowledgeArticles(session.token, cursors[cursors.length - 1], signal), enabled: manager, retry: false });
  const article = useQuery({ queryKey: ["knowledge", session.key, "detail", selected],
    queryFn: ({ signal }) => api.knowledgeArticle(selected!, session.token, signal), enabled: manager && selected !== null, retry: false });
  const mutation = useMutation({ retry: false, mutationFn: async ({ attempt, signal }: { attempt: Attempt; signal: AbortSignal }): Promise<string> => {
    if (attempt.kind === "save") return (await api.saveKnowledge(session.token, attempt.body, attempt.key, signal)).id;
    if (attempt.kind === "index") { await api.indexKnowledge(attempt.id, session.token, attempt.version, attempt.revision, attempt.key, signal); return attempt.id; }
    return (await api.changeKnowledge(attempt.id, session.token, attempt.kind, attempt.version, attempt.revision, attempt.key, signal)).id;
  } });

  async function send(attempt: Attempt) {
    if (locked.current) return;
    locked.current = true; setBusy(true); setError(null); setNotice(""); pending.current = attempt;
    controller.current = new AbortController();
    try {
      const id = await mutation.mutateAsync({ attempt, signal: controller.current.signal });
      if (controller.current.signal.aborted) return;
      pending.current = null; setUncertain(false); setEditing(false); setSelected(id);
      setNotice(attempt.kind === "save" ? "Draft saved. Index it before publishing." : attempt.kind === "index" ? "Keyword index is ready for this version." : attempt.kind === "publish" ? "Version published." : "Publication archived.");
      await client.invalidateQueries({ queryKey: ["knowledge", session.key] });
    } catch (failure) {
      if (controller.current?.signal.aborted) return;
      const safe = failure instanceof ApiError ? failure : new ApiError(0, "network_error", "Unable to confirm the request.");
      setError(safe);
      const ambiguous = safe.status === 0 || safe.status >= 500 || safe.code === "invalid_response";
      setUncertain(ambiguous);
      if (!ambiguous) pending.current = null;
      if (safe.status === 409) await client.invalidateQueries({ queryKey: ["knowledge", session.key] });
    } finally { locked.current = false; setBusy(false); }
  }

  if (!manager) return <ErrorPanel error={new ApiError(403, "forbidden", "Only managers can manage knowledge.")} />;
  const current = article.isFetching || article.isError ? undefined : article.data;
  const frozen = busy || uncertain;
  function editCurrent() {
    if (!current || current.revision === null) return;
    setDraft({ title: current.version.title, body: current.version.body, scope: current.version.scope,
      source_kind: current.version.source_kind, source_reference: current.version.source_reference,
      license_note: current.version.license_note, article_id: current.id, expected_revision: current.revision });
    setEditing(true); setNotice(""); setError(null);
  }
  function action(kind: "index" | "publish" | "archive") {
    if (!current || current.revision === null) return;
    const version = kind === "archive" ? current.published_version_id : current.version.id;
    if (version) void send({ kind, key: crypto.randomUUID(), id: current.id, version, revision: current.revision });
  }
  return <>
    <header className="page-heading"><div><p className="eyebrow">Knowledge operations</p><h1>Knowledge library</h1>
      <p className="muted">Create reliable sources for the support team and control what is published.</p></div></header>
    {notice && <p role="status" className="analysis-notice">{notice}</p>}
    {error && <ErrorPanel error={error} />}
    {error?.status === 409 && editing && current?.revision !== null && current?.revision !== undefined && <div className="analysis-alert">
      <p>The article changed while you were editing. Your draft is retained. Review the current article before using its latest revision.</p>
      <details><summary>Show current version {current.version.number}</summary><strong>{current.version.title}</strong><p className="text-content">{current.version.body}</p></details>
      <button className="button secondary" disabled={frozen} onClick={() => { setDraft({ ...draft, expected_revision: current.revision! }); setError(null); }}>Use current revision</button>
    </div>}
    {uncertain && <div className="analysis-alert"><p>The previous request may have completed. Retry the original request to confirm it.</p>
      <button className="button secondary" disabled={busy} onClick={() => pending.current && void send(pending.current)}>Retry previous request</button></div>}
    <div className="knowledge-layout">
      <section className="panel knowledge-list" aria-labelledby="library-heading">
        <div className="panel-heading"><h2 id="library-heading">Articles</h2><button className="button secondary" disabled={frozen || editing} onClick={() => { setSelected(null); setDraft(emptyDraft); setEditing(true); setNotice(""); setError(null); }}>New article</button></div>
        {list.isFetching && <p className="knowledge-padding" role="status">Loading articles…</p>}
        {list.isError && <ErrorPanel error={list.error as ApiError} retry={() => void list.refetch()} />}
        {list.data && !list.isFetching && !list.isError && <>
          {list.data.items.length === 0 && <p className="knowledge-padding muted">No articles on this page.</p>}
          <ul className="knowledge-items">{list.data.items.map((item) => <li key={item.article_id}>
            <button type="button" className={selected === item.article_id ? "selected" : ""} disabled={frozen || editing} onClick={() => { setSelected(item.article_id); setError(null); setNotice(""); }}>
              <strong>{item.title}</strong><span>{item.scope} · {item.status} · v{item.number}</span></button>
          </li>)}</ul>
          <div className="knowledge-pagination"><button className="button secondary" disabled={frozen || editing || cursors.length === 1} onClick={() => { setCursors(cursors.slice(0, -1)); setSelected(null); }}>Previous</button>
            <button className="button secondary" disabled={frozen || editing || !list.data.next_cursor} onClick={() => { setCursors([...cursors, list.data!.next_cursor]); setSelected(null); }}>Next</button></div>
        </>}
      </section>
      <section className="panel knowledge-detail" aria-labelledby="knowledge-detail-heading">
        {editing ? <form className="write-panel" onSubmit={(event) => { event.preventDefault(); if (!frozen && error?.status !== 409) void send({ kind: "save", key: crypto.randomUUID(), body: { ...draft } }); }}>
          <p className="eyebrow">{draft.article_id ? "New immutable version" : "New article"}</p><h2 id="knowledge-detail-heading">Prepare a draft</h2>
          <p className="muted small">Saving creates a draft. Publication is a separate action.</p>
          <fieldset disabled={frozen}>
            <label htmlFor="knowledge-title">Title</label><input id="knowledge-title" required maxLength={200} value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
            <label htmlFor="knowledge-body">Article content</label><textarea id="knowledge-body" required maxLength={50000} rows={9} value={draft.body} onChange={(e) => setDraft({ ...draft, body: e.target.value })} />
            <label htmlFor="knowledge-scope">Audience</label><select id="knowledge-scope" value={draft.scope} onChange={(e) => setDraft({ ...draft, scope: e.target.value as KnowledgeDraft["scope"] })}><option value="support">Support team</option><option value="management">Management only</option></select>
            <label htmlFor="knowledge-kind">Source type</label><select id="knowledge-kind" value={draft.source_kind} onChange={(e) => setDraft({ ...draft, source_kind: e.target.value as KnowledgeDraft["source_kind"] })}><option value="synthetic">Synthetic</option><option value="licensed">Licensed</option></select>
            <label htmlFor="knowledge-reference">Source reference</label><input id="knowledge-reference" required maxLength={2000} value={draft.source_reference} onChange={(e) => setDraft({ ...draft, source_reference: e.target.value })} />
            <label htmlFor="knowledge-license">License note</label><input id="knowledge-license" required maxLength={1000} value={draft.license_note} onChange={(e) => setDraft({ ...draft, license_note: e.target.value })} />
            <div className="analysis-actions"><button className="button primary" type="submit" disabled={error?.status === 409}>Save draft</button><button className="button secondary" type="button" onClick={() => { setEditing(false); setError(null); }}>Cancel editing</button></div>
          </fieldset>
        </form> : current ? <div className="knowledge-padding">
          <p className="eyebrow">Version {current.version.number} · {current.version.status}</p><h2 id="knowledge-detail-heading">{current.version.title}</h2>
          <div className="analysis-result-meta"><span>{current.version.scope}</span><span>{current.version.source_kind}</span><span>Revision {current.revision}</span></div>
          <p className="text-content">{current.version.body}</p>
          <dl className="knowledge-provenance"><dt>Source</dt><dd>{current.version.source_reference}</dd><dt>License</dt><dd>{current.version.license_note}</dd><dt>Publication</dt><dd>{current.archived ? "Archived" : current.published_version_id ? "A version is published" : "Not published"}</dd></dl>
          <div className="analysis-alert"><strong>Publication checklist</strong><p>Review the source and create the keyword index before publishing. Changes create a new immutable version.</p></div>
          <div className="analysis-actions"><button className="button secondary" disabled={frozen} onClick={editCurrent}>Create new version</button>
            <button className="button secondary" disabled={frozen} onClick={() => action("index")}>Index this version</button>
            <button className="button primary" disabled={frozen || (!current.archived && current.published_version_id === current.version.id)} onClick={() => action("publish")}>Publish this version</button>
            <button className="button secondary" disabled={frozen || current.archived || !current.published_version_id} onClick={() => action("archive")}>Archive publication</button></div>
        </div> : <div className="knowledge-padding"><h2 id="knowledge-detail-heading">Select an article</h2><p className="muted">Choose a source to inspect its contents and publication state.</p>{article.isFetching && <p role="status">Loading article…</p>}{article.isError && <ErrorPanel error={article.error as ApiError} retry={() => void article.refetch()} />}</div>}
      </section>
    </div>
  </>;
}
