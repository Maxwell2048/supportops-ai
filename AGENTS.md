# Repository working notes

- Read README.md and docs/progress.md before implementation. The original requirements are in docs/planning/project-brief.md.
- Work in milestone order. Record implemented and verified separately; link evidence in docs/progress.md.
- Use synthetic or explicitly licensed data only. Never copy private data or secrets into this repository.
- Enforce role and object authorization on the server. Treat model output and retrieved text as untrusted data.
- Keep uv.lock and package-lock.json updated with dependency changes.
- Do not claim PostgreSQL, Docker, CI, Azure, or AI validation unless the corresponding execution actually succeeded.
- Local checks: `cd backend; uv run pytest` and `cd frontend; npm ci; npm run build` (run each command from its stated directory).
- At each stage end, prepare a detailed first-person Git commit message explaining important changes, reasons, validation and limitations. Use only the user's supplied Git author identity for commits; never invent it. Record the message in docs/commit-notes/. Do not claim a commit or push succeeded without execution evidence.

- Use English for all repository content, code comments, commit messages, PR/issue descriptions, and GitHub-facing communication. Use Chinese only when conversing with the project owner.
- Run `python scripts/check_repository_language.py` before publication; use `--history` when validating a history rewrite. Preserve historical test outcomes and distinguish translation from new execution evidence.
