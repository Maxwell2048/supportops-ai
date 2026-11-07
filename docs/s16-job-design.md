# S16 job implementation plan

Status: design in progress. No job API, worker, or migration has been implemented by this document.

A manager or authorized agent creates a job for a currently visible ticket using its expected version and an idempotency key. Authorization must precede idempotency replay. Creation and the idempotency receipt must commit together. The job records its requesting identity, ticket and input version. Reads must recheck the current actor and ticket scope.

A worker claims one eligible row in a transaction using row locking and a fresh unpredictable lease token. Claims increment attempts. The worker must commit the claim before calling a provider. It must check the requester's current authorization before accessing ticket or knowledge content. Provider calls must not hold a database transaction open.

Completion and renewal must compare the current lease token and expiration using the database clock. A worker whose lease expired or was replaced cannot write a result. The result and succeeded status must share one transaction. Expired jobs may be claimed again until the attempt limit, then become failed. Transient provider errors use bounded retries with a persisted next-attempt time. Permanent failures are stored as safe error categories without ticket or provider text.

Ticket changes, role revocation, and knowledge publication changes require explicit rechecks before result publication. Since S17 citation validation and evidence-free refusal are pending, a generation result cannot be presented as an approved evidence-backed suggestion before those checks exist. Human review remains mandatory.

Acceptance must exercise independent database connections for concurrent claim and duplicate create, process restart after claim, expiry and token fencing, retries and attempt exhaustion, rollback on result insertion, current permissions, and a real worker process. Local and CI evidence must identify the provider mode used.
