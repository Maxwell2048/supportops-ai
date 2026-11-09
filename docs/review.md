# Human review

Staff can read a validated suggestion using the analysis job ID and review it once. The current ticket assignment and cited publication scope are checked on the server. A ticket or source change requires a new analysis. Results created before the validation marker was introduced also require reanalysis.

Accepting a cited draft or sending an edited draft creates one public message, ticket event, audit record and terminal review decision in one transaction. An Idempotency-Key makes the same request replayable. Rejecting records a decision and creates no public message. Evidence-free handoffs can only be rejected; staff can reply independently. Closed or archived tickets cannot be reviewed for publication.

The worker remains mock-only. Review requires human judgment of claim support even for authentic quotations. The interface is a separate delivery step.
