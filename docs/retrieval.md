# Authorized knowledge retrieval

S14 provides PostgreSQL full-text search and exact pgvector cosine search over the same deterministic version chunks. A chunk preserves its version, ordinal, Unicode character offsets, text hash, and source provenance. The current chunker uses 400-character windows with 40 characters of overlap.

Managers build a representation with `POST /api/knowledge/articles/{id}/index`, an `Idempotency-Key`, and a body containing `version_id`, `expected_revision`, and `mode` (keyword or vector). Building a representation does not publish the version or increment the article revision. To index current publications from the backend directory, use `uv run --locked python ../scripts/index_knowledge.py --mode keyword` with the configured synthetic manager account. Vector indexing also builds the keyword representation.

Staff use `GET /api/knowledge/search?q=account%20access&mode=keyword&limit=5`. Agents search current support publications. Managers also search current management publications. Requesters receive 403. SQL applies current scope and publication state before ranking and limiting. Historical chunks survive archive or replacement but leave the candidate set. Responses distinguish authorized published versions from indexed versions and include the score kind, version and chunk provenance. Scores are specific to their mode.

Keyword search requires only PostgreSQL. Vector search uses loopback Ollama with `all-minilm:22m`, a verified model digest, and 384-dimensional L2-normalized embeddings. Start Ollama locally and run `ollama pull all-minilm:22m`. The default endpoint is `http://127.0.0.1:11434`; see `.env.example`. Provider or digest errors return a safe 503. Use only synthetic or explicitly licensed text.

See the [design decision](adr/0010-versioned-retrieval-and-local-embeddings.md) and [execution evidence](evidence/2026-10-27-retrieval.md). Knowledge UI, suggestion generation, formal retrieval evaluation, and approximate indexes remain future work.
