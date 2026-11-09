# Knowledge workspace verification

On 2026-11-09, the manager knowledge workspace passed four focused real-browser cases across desktop and narrow viewports. The manager created a synthetic draft, built its keyword index, published it and archived it. Requester access to the workspace was denied. The full browser suite passed 22 cases with a separate mock worker and isolated PostgreSQL schema. The fixture removed its schema and worker afterwards.

The production build, type checks, 17 component tests and existing API/query/write tests passed. A component test verified that an ambiguous save retains the original payload and idempotency key. The first browser attempt exposed an omitted-null response parsing issue; the parser was corrected and the rerun passed. A separate full-suite attempt overlapped npm ci and failed to find a dependency; after the installation completed, a sequential rerun passed.

The interface exposes current/latest versions and keyword indexing. Historical-version browsing, vector indexing, accessibility audits and real-model evaluation remain open. Source licensing remains a manager responsibility.
