# Initial Git publication

Date: 2026-10-22 (Australia/Perth). The owner supplied repository/identity and authorized commit/push.

- Remote: https://github.com/Maxwell2048/supportops-ai.git, main.
- Author: Maxwell with the explicitly supplied email, repository-local configuration only.
- Legacy initial hash before English conversion:`846a5bdf1fc5c7ec3daeff0bb45bfb69ef1a8cc4`.
- Legacy publication-record tip:`96377cfe239c7812a0efa27cc213468a2b8efc86`.
- Original baseline: 96 files/6804 inserted lines through S08, with [detailed message](../commit-notes/initial-through-s08.txt), not fabricated per-stage history.

Actual original results: git ls-remote confirmed empty remote; git commit --file and git push -u origin main succeeded; remote main matched the initial full hash. The documentation follow-up also pushed and matched its local tip. main tracked origin/main and the worktree was clean.

Before publication,96 candidate files were checked for actual local password/JWT/demo password/DSN; .env was ignored and unstaged. This is not a third-party security audit.

That publication-only turn changed no business code and relied on existing S08 evidence:173 tests and frontend build. It did not rerun or establish remote CI. Successful publication is separate from CI success.

## Owner-requested English replacement

The owner later explicitly requested English for all existing repository files and published commit messages. The two English snapshots replace the original branch history while preserving original author timestamps; legacy hashes above are provenance only, not current branch references. A local-only backup retains the old tip, and an exact remote lease prevents overwriting unexpected work. Conversion checks and execution details: [English evidence](2026-10-22-english-repository.md).
