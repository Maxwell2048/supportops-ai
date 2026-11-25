# Controlled read-only tool use

Analysis jobs let the model choose which read-only tools to call before a draft is written. The server decides what is offered, validates every request, and re-checks authorization for every call. The model never gains a capability that the requesting staff member lacks, and no tool can write.

## Flow

1. The worker claims a job and checks, as before, that the requesting agent or manager is active, can still see the ticket, and that the ticket version is unchanged.
2. The planner receives the ticket text, the tool definitions and earlier observations. It returns tool calls or an empty list when it is ready to draft. Up to three planning rounds and four budgeted calls are allowed per job.
3. Each requested call is checked against the allow-list and a strict argument schema. Unknown tools are rejected as `tool_not_allowed`; extra, missing, mistyped or out-of-range arguments are rejected as `invalid_arguments`. The planner sees the rejection reason and the failing field and error type, never echoed values, so it can correct the next call.
4. Each allowed call runs in its own short transaction that first renews the job lease, then reloads the actor, re-checks ticket visibility, version and archive state, and only then reads data. Losing the lease stops the worker without writing a result. Lost access, reassignment, deactivation or a changed ticket fails the job as `access_or_ticket_changed`.
5. Unless the planner already ran it, the server runs the baseline authorized title search outside the call budget. Its passages are kept first under the 20-passage evidence cap, so tool use can add evidence but never yields less than the fixed pipeline.
6. The drafter receives only passages returned by authorized searches, plus ticket history as separate untrusted context. Citations are validated against those passages, and completion re-locks the sources and re-checks access as before. A human still decides whether anything is sent.

## Tools

| Tool | Arguments | Returns | Boundaries |
|---|---|---|---|
| `search_knowledge` | `query` (1-500 chars), `limit` (1-5) | Passages with chunk, version, title and text | Uses the same current-scope keyword retrieval as the API. Incomplete indexing stops the job. |
| `ticket_history` | `limit` (1-10) | Public messages (from requester or staff, 1,000 characters each) and event types | Bound to the analyzed ticket; it has no ticket parameter. Internal notes, user IDs and emails are excluded because the draft becomes a public reply. |

Providers without a `plan` method keep the previous behavior: the server runs one baseline search on their behalf.

The loop is orchestrated by a hand-written loop by default. `ANALYSIS_LOOP=langgraph` selects an equivalent LangGraph graph that uses the same server-side enforcement; see [optional LangGraph orchestration](langgraph-tool-loop.md).

## Trace

`analysis_jobs.tool_trace` (migration 0010) records each call: round, planner (`model` or `system`), tool name, status (`ok`, `rejected`, `budget_exceeded`, `stopped`), result count, validated arguments, and for rejections the reason and failing field types. Rejected arguments are not stored. The suggestion endpoint returns the trace as `tool_calls`, and the review workspace lists it as text.

## Design notes

See [ADR 0011](adr/0011-controlled-read-only-tool-use.md) and [execution evidence](evidence/2026-11-23-agent-tools.md). The tool loop does not establish model quality; a small local model in the evidence repeatedly requested out-of-range limits and its own keyword queries found no passages.
