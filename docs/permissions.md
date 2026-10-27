# Permissions and user stories (S01 baseline draft)

Single organization with fixed demo accounts. No public registration, role editing, or administrator-registration endpoint. Managers can handle all tickets; agents can handle only tickets currently assigned to them; requesters can read only tickets they created.

| Action | Requester | Agent | Manager |
|---|---|---|---|
| Create ticket | Yes; identity determines author | No | No |
| List/details/public messages | Own tickets | Currently assigned tickets | All |
| Internal notes and ticket events | Hidden | Currently assigned tickets | All |
| Public reply | Own, not closed/archived | Assigned, not closed/archived | Not closed/archived |
| Assign/change priority/archive | No | No | Yes |
| Change status | Explicit reopening only | Allowed transitions on assigned tickets | Allowed transitions on all tickets |
| Create/read AI jobs and review suggestions | No | Currently assigned tickets | All |
| Search knowledge | No UI/API access | Published, support scope | Published, support/management scope |
| Create/publish/archive knowledge | No | No | Yes |
| Management dashboard and audit | No | No | Yes |

Knowledge scopes are initially support and management. Historical citations must not bypass scope authorization: agents cannot read old suggestions containing management-only sources. Generation records the requesting role and knowledge scope; reassignment requires current read authorization to be recalculated. Requesters see human public replies, never internal suggestions or source snapshots.

## Stories and negative cases

- Requester A creates a ticket and reads replies. Accessing B's details, messages, or child resources returns 404.
- Agent A handles an assigned ticket. After transfer to B, A receives 404 for details, historical jobs, suggestions, and review writes.
- Managers assign tickets and publish knowledge. Missing/inactive assignees return 422; requesters cannot be assignees.
- Injected requester_id, assignee_id, role, or other forbidden fields return 422 rather than silently granting privileges.
- Requester detail responses exclude internal notes, events, jobs, and audit at the API boundary, not merely in the UI.
- Managers still obey transition rules and transactional audit; pending AI drafts cannot be published directly.

## Response policy and implemented scope

Missing/invalid/expired sessions return 401; a prohibited role-level feature returns 403; missing or invisible objects return 404. Authorization precedes version/idempotency conflicts. Lists, counts, search, and child resources share the same visibility scope.

S06 implements password hashing, JWTs, and read scopes; see [authentication](auth.md). Each request checks current active/role and ownership in the database. Requester responses exclude internal messages/events; events require staff role and object access. S07 verifies write authorization; S08 verifies manager-only ticket audit. S13 verifies knowledge API scopes/publication: agents read only active support publications and explicitly referenced previously published support versions while current article scope remains support. Archiving or changing current scope to management denies those old references. Drafts/management snapshots remain hidden, and manager-only history endpoints do not expose a general version directory to agents. See [knowledge authorization](knowledge.md). Knowledge UI, retrieval, AI jobs and management metrics remain planned.

The S09 frontend stores JWTs in memory and unmounts private page state on logout/user changes. Login and read-only ticket views are locally verified; S10 caches are session-owned, cleared at session boundaries, and revalidated on navigation/focus/reconnect. Hidden buttons are not authorization.
