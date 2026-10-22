# English repository conversion

Date: 2026-10-22 (Australia/Perth). The owner explicitly requested English for the entire already-published repository, including existing commit messages, documentation, comments, application text, and test data. Conversation with the owner remains Chinese.

## Changes

- Translate README, all 17 archived requirements sections, design/operating guides, ADRs, learning notes, acceptance criteria, historical execution records, and saved commit messages. Preserve recorded dates, counts, limitations, and requirements rather than upgrading claims during translation.
- Translate API prompts, synthetic seed/fixture text, HTTP smoke payloads, static UI copy, and HTML metadata; set document lang=en. Update matching test assertions. No business rules, dependencies, migration schema, account state, or existing local database history are changed.
- Save the language policy in AGENTS.md and Git guidance. Add scripts/check_repository_language.py to inspect publishable files and optionally all snapshots/messages reachable from HEAD. Its character scan is a guard against CJK regressions, not semantic proof of English prose. Ignored local credentials/data are excluded.
- Replace the two previously published commits with English snapshots and detailed English messages, preserving original author identity/timestamps. Reconstruct trees without discarding the worktree. Keep the old tip in a local-only backup ref and update remote main only with its exact expected hash as a lease. The backup is not pushed.

## Actual verification before publication

From backend: uv run --locked python ../scripts/test_backend.py -q -> **173 passed in 7.16s, zero skips**, using real PostgreSQL and isolated test schemas.

From frontend: npm ci -> 24 packages added, zero vulnerabilities reported in that run; npm run build -> TypeScript/Vite 8.3.4 passed, 15 modules, 113ms Vite build.

Repository character scan passed before staging. Python syntax, relative Markdown links, existing trace JSONL, whitespace, and local-secret exclusion are checked before publication. After reconstruction, --history checks both English commit messages and every reachable historical blob; remote main is compared with local HEAD after the lease-protected push. Git execution results belong to the actual Git history/terminal verification, not a claim inferred from file edits.

## Original publication provenance

Before conversion, remote main was independently read as 96377cfe239c7812a0efa27cc213468a2b8efc86, and the original initial commit was 846a5bdf1fc5c7ec3daeff0bb45bfb69ef1a8cc4. Those are legacy identifiers, not links to the new branch history. Original publication checks remain historical evidence; rewritten hashes change by design.

This does not erase GitHub's possible cached/unreachable old objects or claim to verify remote CI, branch protections, Azure, AI, business pages, or browser E2E. No new real HTTP workflow was necessary for wording-only changes; the complete real-database regression and frontend build were rerun.
