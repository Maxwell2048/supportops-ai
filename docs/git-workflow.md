# GitHub setup and stage commit policy

Date: 2026-10-22. The owner requests detailed first-person commit messages for each stage. GitHub-facing comments, PR/issue descriptions, commit messages, repository documentation, source comments, fixtures, and UI/API text use English. Conversation with the owner uses Chinese.

## Repository setup

| Setting | Initial recommendation |
|---|---|
| Owner/name | Personal account; supportops-ai |
| Description | AI-assisted support ticket platform with role-based access, auditable workflows, and human-reviewed replies. |
| Visibility | Private initially; consider Public after content/demo review |
| Initialize README/.gitignore/license | No; import existing local content into an empty remote |
| Default branch | main, matching local |

See [GitHub local-code import](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github). Private is this project's recommendation, not a platform requirement. Choose a license separately before public reuse.

The owner supplied https://github.com/Maxwell2048/supportops-ai.git and the author identity Maxwell. Configure user.name/user.email only in this repository. Repository ownership, commit authorship, and GitHub authentication are separate settings. Use exactly the supplied email, never an inferred identity.

## Initial history and English conversion

The original first commit contained the accumulated baseline through S08, rather than fabricated per-stage history. [Initial message](commit-notes/initial-through-s08.txt), [S08 message](commit-notes/S08.txt), and [publication evidence](evidence/2026-10-22-git-publication.md) document that scope.

The owner subsequently explicitly requested English throughout the already-published repository. Replace the two published snapshots/messages with English equivalents, retain original author dates, and keep a local-only backup of the old tip. Before updating the remote, verify its expected hash and use an exact --force-with-lease. Never force past newly observed remote work. Do not push the old-language backup ref. Old evidence identifiers remain labeled legacy, not current links.

Future stages: review diff/exclusions -> run acceptance -> update progress/evidence -> write a detailed first-person English message -> commit with supplied identity -> push to the authorized remote. Messages explain the problem, important changes/reasons, actual verification, limits, and next step. Disclose AI assistance rather than claiming all code was independently handwritten.

GitHub Actions and branch protection require actual execution checks. A successful push is not a passing CI run.
