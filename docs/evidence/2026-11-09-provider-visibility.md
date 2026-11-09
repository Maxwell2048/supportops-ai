# Generation source visibility

Implemented: the review workspace reads the generation provenance returned by the API and distinguishes the demo provider, a local model, a custom provider, a no-model result, and older results without recorded provenance. Model names are rendered as text. This makes the default demo behavior visible to reviewers.

Verified on 2026-11-09: a clean `npm ci`, `npm run build`, `npm run test:types`, and all 17 component tests passed. Four browser cases passed across desktop and narrow layouts against the real local API and mock worker; they checked the demo-provider and no-model labels. An initial sandboxed `npm ci` stalled and was interrupted; the clean install and tests then succeeded with network access. The existing backend was unchanged by this stage.

Limitations: the label reports stored provenance, not a guarantee of model quality. Local model accuracy and independent review of the synthetic retrieval labels remain open. Azure is deferred to the handbook.
