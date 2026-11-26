# README refresh verification

Implemented on 2026-11-26: the root README was rewritten as a project landing page (tagline, badges, screenshots, features by role, architecture diagram, quick start, testing, tech stack, structure, documentation index, roadmap and contribution rules). Stage-by-stage test history moved out of the README; it remains in [progress](../progress.md) and the dated evidence files. Three screenshots were added under `docs/images/readme/`.

## Screenshots

The screenshots come from a disposable local stack that used only synthetic data:

- `docker compose -p supportops-readme -f compose.full.yaml up --build -d --wait` with a throwaway env file (random PostgreSQL password, JWT secret and demo password) outside the repository, web port 8091. The separate project name kept the owner's existing `supportops-app` stack and volume untouched.
- `docker compose ... exec -T -e DEMO_PASSWORD api python -m supportops.compose_demo` activated the five synthetic accounts.
- Through the public API, the manager created, published and keyword-indexed the four bundled synthetic articles from `data/knowledge/synthetic-v1.json`. Two synthetic requesters created four tickets, and the manager assigned and prioritized three of them.
- As `agent-a`, one analysis job ran on "Synthetic account remains unavailable" with the default mock provider. It succeeded with one citation and two read-only tool calls.
- Playwright (the project's pinned `@playwright/test`, Chromium, 1440x900) captured the manager ticket list, the agent's suggestion panel and the manager knowledge library.
- `docker compose -p supportops-readme ... down -v --rmi local` removed the containers, volume, network and locally built images afterwards.

The response draft in the screenshot is the mock provider's fixed text; it does not show model quality.

## Checks

- All 52 relative links and image paths in the README resolve to files in the repository, and every in-page anchor matches a heading.
- The README rendered through the GitHub Markdown API with the expected tables, note callout and images. The Mermaid diagram parsed and rendered with Mermaid 11.4.1 in a local page.
- `python scripts/check_repository_language.py`: "Language character check passed: 292 files, 0 commits, 0 historical blobs."
- The test counts quoted in the README come from the GitHub Actions run for `main` at `cfd17d2` (push, 2026-11-26): 421 backend tests passed; frontend API, query and write tests passed 17, 11 and 6; Vitest passed 19 component tests; Playwright passed 24 end-to-end tests.

## Not verified

- The quick start was not repeated from a fresh clone on another machine, and the macOS and Linux shells were not tried.
- The manual development setup commands were collected from the existing guides and were not re-run for this change.
- The README's rendering on github.com itself is checked only after publication.
