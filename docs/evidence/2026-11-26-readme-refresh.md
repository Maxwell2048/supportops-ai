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

## Bilingual README, demo animation and license

Implemented later on 2026-11-26:

- **License:** an MIT `LICENSE` file (copyright Maxwell, 2026). The README license section and badge now point to it.
- **Translation:** `README.zh-CN.md`, a Simplified Chinese translation of the README. Both files open with language badges that link to each other. The project owner approved this single translated file as an exception to the English-only rule. `AGENTS.md` records the exception. `scripts/check_repository_language.py` skips that one path, and it now also treats GIF files as images rather than text.
- **Richer README content:**
  - a table of contents and a demo animation;
  - highlight cards and a screenshot gallery;
  - a review sequence diagram and a ticket state diagram;
  - a "by the numbers" table, a configuration table and an API overview;
  - MCP client setup, a CI job table and an FAQ.

The animation and the extra requester screenshot came from the same kind of disposable stack (`supportops-readme`, port 8091, throwaway env file outside the repository):

1. I activated the synthetic accounts, then published and indexed the four bundled articles and created four synthetic tickets.
2. Playwright recorded agent-a running the analysis, checking the evidence, rewriting the draft and sending it as an edited reply. It then captured requester-a's view of the reply.
3. ffmpeg trimmed the 27.4-second recording and converted it to an 800-pixel, 8 fps GIF of about 2.9 MB.
4. The stack, its volume and its locally built images were removed afterwards.

A 390x844 phone capture showed the ticket table wider than the viewport. It is listed as a known limit and not used as a screenshot.

Checks:

- The language check passed with 298 files.
- In both README files, every relative link and image path resolves and every in-page anchor matches a heading (63 and 64 links).
- All six Mermaid diagrams (three per language) rendered with Mermaid 11.4.1.
