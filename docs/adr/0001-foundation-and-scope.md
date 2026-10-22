# ADR 0001: Repository location, scaffold, and stage boundaries

Date: 2026-10-16. Status: accepted.

## Context

The handoff described its old location as another project's reference directory. The actual `D:\SupportOps AI` directory contained only that handoff, and the user requested a repository and foundation.

## Decision

- Use `D:\SupportOps AI` as the independent repository root without another nested directory. Preserve the requirements snapshot in docs/planning/project-brief.md; it was later translated to English under the owner's language policy.
- Root README describes current state and real commands; docs/progress.md tracks acceptance.
- Create FastAPI health endpoints and a React/TypeScript/Vite static scaffold. Verify available dependencies before pinning them and generating both lockfiles.
- Use existing Python 3.14 and Node 22. Limit Python to the 3.14 series; a future database/inference compatibility change requires an ADR and regression checks.
- At this stage, do not create remotes, cloud resources, or automated publication. Continue M0 -> M1.
- Start Compose with PostgreSQL/pgvector pg17; S05 will pin a verified digest. Do not claim reproducibility before checking the image.

## Consequences

Validate the toolchain before claiming business capabilities. Initial CI does not satisfy S23 database/migration/cross-role acceptance.
