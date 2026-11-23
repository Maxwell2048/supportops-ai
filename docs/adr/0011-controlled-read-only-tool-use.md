# ADR 0011: Let the model choose read-only tools under server control

Status: accepted on 2026-11-23.

The fixed analysis pipeline ran one keyword search on the ticket title. I wanted the model to decide what extra context it needs, as an agent would, without weakening the authorization and review guarantees established in S16-S19.

I chose a server-side allow-list of two read-only tools instead of letting the model call API routes or SQL. The model only proposes calls; the worker validates names and arguments with strict schemas and a per-job budget, then executes each call in its own transaction after renewing the lease and re-checking the requesting staff member's current access. Authorization therefore does not depend on model output, on prompts, or on the state observed when the job started. Write tools do not exist, so a request such as a reply or status change is rejected as an unknown tool.

Tool parameters never name another ticket. Ticket history is bound to the job's ticket and excludes internal notes, because a draft becomes a public reply and agents can see other customers' tickets. Retrieval reuses the existing scoped search, so restricted knowledge cannot reach the planner.

I kept a baseline title search that the planner cannot remove and protected its passages from the evidence cap. This makes tool use additive: it can supply more evidence and context but cannot make retrieval worse than the earlier pipeline. Rejection details return field locations and error types to the planner so it can self-correct, but never echo values. The trace is stored for reviewers and operators.

I used a stateless planning call that sends prior observations each round, and a separate structured-output call for the final draft. This keeps one validation path for drafts and avoids depending on multi-turn tool message formats. Native Ollama tool calling is used for planning. Alternatives considered were a free-form ReAct text protocol (harder to validate), giving the model direct API tokens (authorization by prompt), and executing tools inside a single long transaction (holds locks during inference).

Consequences: each job makes up to three extra model calls, so latency grows. The budget and the 60-second adapter timeout bound it, and each tool call renews the 180-second lease. Model quality, query quality and adversarial behavior remain open evaluation work.

References: [Ollama chat API tool calling](https://docs.ollama.com/api/chat), [Pydantic strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/).
