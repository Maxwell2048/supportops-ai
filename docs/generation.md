# Generation provider boundary

S15 defines a structured suggestion with category, priority, draft, citations and human verification items. Unknown fields and malformed results are rejected. Ticket and evidence are serialized as data with bounded input sizes. A deterministic mock supports isolated tests. The loopback-only Ollama adapter uses structured output, disables streaming and redirects, and reports distinct unavailable, timeout and invalid-output failures without provider details.

The adapter uses a 5-second connection timeout and 60-second HTTP operation timeout. It has no automatic retries. The local model name is an explicit constructor argument. The integration uses transport-simulated responses and does not yet establish behavior or quality of a real generation model.

The contract does not establish authorization or citation authenticity. Callers must supply currently authorized content. S17 will validate source identifiers and contiguous quotations and define evidence-free refusal. No route or worker calls this adapter yet. AI output remains untrusted and requires human review.
