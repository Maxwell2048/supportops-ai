# Data and execution modes (S03 baseline draft)

The repeatable minimal seed was verified against real PostgreSQL: five synthetic accounts, one ticket, and its creation event. New seed accounts are disabled by default; S06 explicitly activated five local demo accounts through a separate script. Use fictional organizations, accounts, and sample products only. Do not import private resumes, customer tickets, databases, or secrets.

- Development target: two requesters, two agents, one manager; approximately 100 tickets and 20-30 knowledge articles, including reassignment, internal notes, closing, and reopening cases.
- Generator target: seed 42 and stable UUIDs. Demo credentials come from ignored local configuration and must not be reused in production. Repeat runs must not duplicate records; relevant checks belong to S05/S07.
- SQL experiments: an additional 5,000 synthetic rows, with generator version and environment recorded separately from evaluation data.
- AI evaluation target: 30 manually checked questions, split into 20 development and 10 holdout questions, plus separate authorization, injection, and invalid-citation cases. Do not claim completed labeling before S21.
- Mock mode: deterministic responses for timeouts, missing evidence, invalid citations, and provider failures; clearly label the mode in the UI.
- Local mode: real embeddings and a local model; verify model, dimension, version, and license in S14/S15.
- CI target: real PostgreSQL plus mock inference. PostgreSQL tests and frontend build are configured; remote execution is not verified and AI/mock business functionality is not implemented.
- Cloud target: isolated synthetic data with an explicitly labeled mock if used. No cloud environment exists yet.

External datasets require a source, license, permitted scope, and processing description. There are currently no external dataset dependencies. Repository seed text and test fixtures use English. Existing local development database history is not silently rewritten during repository translation.

S13 provides four original English examples in knowledge/synthetic-v1.json, with explicit synthetic source references and provenance notes. Three are support scope and one management scope. The separate importer creates unpublished immutable drafts by default and does not reset prior publications/archives. See [knowledge lifecycle](../docs/knowledge.md). These four examples are not the planned evaluation corpus or completed20/10 labels.
