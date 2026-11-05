# ADR 0010: Version retrieval representations and use local embeddings

Status: accepted in S14.

I chose deterministic text chunks and PostgreSQL full-text ranking as the reproducible baseline. Both search modes apply the current publication relation before ranking, so a stale chunk cannot grant access and an unauthorized hit cannot consume the result limit.

A representation manifest becomes visible in the same transaction as its chunks and vectors. The embedding profile identifies provider, model digest, dimension, normalization, and license. Vectors are compared only within that profile. SQL enforces the profile dimension and unit norm. Exact cosine search keeps the initial comparison reproducible for the small synthetic corpus. An approximate index needs separate performance and recall evidence.

Ollama stays on loopback and checks the pinned model before and after embedding. The adapter rejects truncated, malformed, mismatched, non-finite, or zero-length vectors and bounds each HTTP request. Provider failures leave the representation transaction uncommitted. Retrieved content is untrusted text.

References: [Ollama embed API](https://docs.ollama.com/api/embed), [Ollama model registry](https://ollama.com/library/all-minilm), [Apache-2.0 model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2), [pgvector](https://github.com/pgvector/pgvector).
