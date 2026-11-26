docs(readme): add an MIT license, a Chinese README and a richer landing page

I added the MIT license, so the project can be reused and GitHub shows the license in the About panel. The README license section and a license badge now point to the LICENSE file.

I added README.zh-CN.md, a Simplified Chinese translation of the README. Both files open with language badges that link to each other. The project owner approved this one translated file as an exception to the English-only rule, so I recorded the exception in AGENTS.md. scripts/check_repository_language.py now skips exactly that path, in both the working tree and the history checks. The checker also treats GIF files as images rather than text, because the demo animation's bytes otherwise decode into CJK code points.

I made the README a fuller landing page:
- a table of contents and a recorded demo of an agent reviewing and sending a draft;
- highlight cards and a screenshot gallery that adds the requester's view;
- a review sequence diagram and a ticket state diagram;
- a "by the numbers" table, a configuration table from .env.example and an API overview;
- MCP client setup, a CI job table and an FAQ.
The Chinese file mirrors all of it.

I recorded the demo from a disposable Compose project (supportops-readme, port 8091) with a throwaway env file outside the repository, using synthetic accounts, the four bundled synthetic articles and four synthetic tickets. Playwright recorded agent-a running the analysis, rewriting the draft and sending it, then captured requester-a's view. ffmpeg turned the 27-second recording into an 800-pixel, 8 fps GIF of about 2.9 MB. I then removed the containers, volume and locally built images. A phone-sized capture showed that the ticket table is wider than a 390-pixel viewport; I listed that as a known limit instead of showing it.

Validation: the language check passed with 298 files. In both README files, every relative link and image path resolves and every in-page anchor matches a heading. All six Mermaid diagrams rendered with Mermaid 11.4.1.

Limitations: the quick start was not repeated from a fresh clone on another machine. The demo shows the mock provider's placeholder draft before it is rewritten. The translation must be kept in step with README.md by hand.
