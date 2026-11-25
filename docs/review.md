# Human review

Staff can read a validated suggestion using the analysis job ID and review it once. The current ticket assignment and cited publication scope are checked on the server. A ticket or source change requires a new analysis. Results created before the validation marker was introduced also require reanalysis.

Accepting a cited draft or sending an edited draft creates one public message, ticket event, audit record and terminal review decision in one transaction. An Idempotency-Key makes the same request replayable. Rejecting records a decision and creates no public message. Evidence-free handoffs can only be rejected; staff can reply independently. Closed or archived tickets cannot be reviewed for publication.

A review request is checked in this order: the reviewer's current active staff role, a lock on the analysis job, the current ticket scope with a row lock, and then the idempotency claim. If the same reviewer already completed a review with the same key and body, the stored receipt is returned without re-validating evidence, so a retry after a lost response still reports the sent reply even if a cited article was archived in the meantime. A reassigned or downgraded reviewer is still denied before any replay. For a new claim, cited evidence is re-validated and current sources are share-locked before anything is written; a failed validation rolls back the claim placeholder with the rest of the request.

The worker remains mock-only. Review requires human judgment of claim support even for authentic quotations. The ticket detail workspace exposes analysis history, source quotations and review decisions for staff.
