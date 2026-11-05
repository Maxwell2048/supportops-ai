# S14 retrieval verification

Local execution: 2026-10-27 (Australia/Perth).

- Backend: `uv run --locked python ../scripts/test_backend.py -q --tb=short` passed 262 tests, zero skips, on PostgreSQL. Integration tests used deterministic mock embeddings with the real pgvector extension.
- Frontend: clean npm install, production build, type checks, 46 client/component tests and 12 Chromium E2E cases passed. Knowledge E2E exercised actual HTTP keyword indexing and search across publication and scope changes. The browser runner reported removing its disposable schema.
- Live embedding: `uv run --locked python ../scripts/check_retrieval.py` used Ollama 0.33.3 and pgvector 0.8.7 in a disposable schema. Model `all-minilm:22m` digest `1b226e2802dbb772b5fc32a58f103ca1804ef7501331012de126ab22f67475ef` produced four 384-dimensional vectors for four synthetic chunks. Reindexing reused the representation. Data survived connection pool disposal and reopening, and archiving reduced agent-visible indexed versions from three to two. The live runner removed its disposable schema.
- For the three synthetic queries `account access`, `collect diagnostic context`, and `verify a resolution`, both modes ranked the corresponding sample first. This smoke check has no labeled holdout and does not measure accuracy. The first cold model request hit the timeout and returned a safe 503. The live rerun passed using the same timeout.
- Development upgrade 0004 to 0005 passed readiness and preserved existing business rows. All four knowledge drafts stayed unpublished. The keyword indexing CLI reported zero current publications and made no development vector writes.

See [remote CI baseline and fix](2026-10-27-remote-ci.md). The S14 publication run is independently checked against its exact commit. Real model execution was local. Formal relevance evaluation, scale benchmarks, generation, and cloud deployment remain unverified.
