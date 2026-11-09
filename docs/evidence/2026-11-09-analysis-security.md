# Analysis security regression

On 2026-11-09, 299 backend tests passed with zero skips against PostgreSQL and 15 frontend component tests passed. Synthetic regression cases checked requester and unassigned-agent denial, ticket changes during generation, untrusted source instructions and HTML-like source text. Existing citation tests cover wrong source IDs, changed publication and management-scope exclusion.

An adversarial simulated provider returned instructions to close a ticket. The result stayed a draft; it did not close the ticket or send a public message without review. The browser rendered source markup as text. These checks do not show that a real model resists prompt injection or that a human will identify a harmful suggestion. A labeled adversarial model evaluation and broader concurrent authorization regression remain outstanding.
