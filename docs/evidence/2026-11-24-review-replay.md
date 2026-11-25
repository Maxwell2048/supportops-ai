# Review replay after a source change

Implemented: `review()` in `backend/src/supportops/reviews.py` now claims the idempotency key immediately after the current role and ticket-scope checks and returns a stored receipt before `validated_suggestion()` runs. Before this change, evidence was re-validated first, so a completed review retried after its cited article was archived returned 409 `stale_suggestion` although the public reply had been sent. See [human review](../review.md).

## Automated checks on 2026-11-24

- Backend: 342 tests passed with zero skips against local PostgreSQL through `scripts/test_backend.py`, which uses a dedicated `_test` database and isolated schemas. This is the 339 tests from the [agent-tools stage](2026-11-23-agent-tools.md) plus 3 new integration cases.
- The new cases cover: an accepted review, then archiving the cited article in a separate committed transaction, then a retry with the same key and body that returns the identical receipt while the message count stays 1; a new key after archiving that still returns 409 `stale_suggestion`, adds no message and leaves no idempotency record for that key after rollback; and a replay of the original key that returns 404 after reassignment and 403 after a role downgrade.
- Regression check: with the original `reviews.py` restored temporarily, the focused review suite ran 9 tests and only `test_completed_review_replays_after_cited_source_is_archived` failed, with 409 `stale_suggestion`. With the change applied, all 9 passed.
- Frontend checks were not run; this change does not touch the frontend.

## Limitations

- For a new claim, an idempotency key reused with a different body now reports 409 `idempotency_conflict` before evidence checks, where it previously reported `stale_suggestion` when sources had also changed. Both are 409 and neither writes anything.
- A replay returns the original receipt. It does not state that the cited sources are still current; a fresh suggestion read shows the current state.
- These are local PostgreSQL integration tests with synthetic data and the mock provider. Browser behavior after a lost response was not re-run.
