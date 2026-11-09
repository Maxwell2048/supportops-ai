# Citation validation and human handoff

The worker searches currently published, role-authorized knowledge with the ticket title and the keyword baseline. It requires all currently authorized publications to have a keyword index before deciding that no evidence was found. If no matching chunks are found, it stores a fixed handoff requiring human review and does not invoke the provider.

When evidence exists, the worker passes the exact retrieved chunk and version IDs and text to the provider. Every citation must identify one of those provided chunks, match its version, and contain a nonblank contiguous quote from the chunk. Invalid citations fail the job. Malformed provider output and provider errors retain their own failure categories. The worker checks current publication and scope again under article locks before storing the result and compares each chunk with its original version body slice. Changed knowledge fails the job.

A matching quotation establishes source authenticity, not that the draft's claims are supported. The separate suggestion endpoint exposes validated results to currently authorized staff for human review. The mock provider and synthetic data exercise this path; local generation inference remains unverified. See [execution evidence](evidence/2026-11-07-citations.md).
