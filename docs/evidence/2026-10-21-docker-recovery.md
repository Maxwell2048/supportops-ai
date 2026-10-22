# Docker recovery

Date: 2026-10-21 (Australia/Perth). Docker Engine and actual container execution recovered successfully.

## Diagnosis

Docker info could not connect to desktop-linux. Startup logs showed sailor-ingest.sock access failure and a single-file query returned Windows error1920. Read-only inspection found the backend stopped and four zero-byte ReparsePoint runtime endpoints under Docker/run; user ACLs included full control. This did not prove NTFS damage or bad permissions.

An [OpenAI issue report](https://github.com/openai/codex/issues/52698) described similar MSIX/AppData child-process virtualization behavior and recommended Explorer startup. This was a diagnostic lead, not independent proof of this machine's root cause.

## Recovery

Start the confirmed Docker Desktop executable through Windows Explorer. After12 seconds Engine 29.7.2 responded. No socket/runtime directory/config/image/volume was renamed or deleted. No factory reset, reinstall, or WSL reset.

The startup-context change restored this machine and is consistent with the report. Windows-reboot persistence remains unverified; no underlying Docker/Codex defect fix is claimed.

scripts/start-docker.ps1 checks the local engine first, starts through Explorer only when necessary, and polls with a bound. It does not reset data/system settings.

| Check | Result |
|---|---|
| docker info --format '{{.ServerVersion}}' |29.7.2 |
| OSType / Driver |linux / overlayfs |
| docker run --rm --network none --name supportops-docker-smoke-20261021 hello-world | Exit0, Hello from Docker |
| docker ps -a by smoke name | No leftover; --rm worked |
| pwsh -NoProfile -File scripts/start-docker.ps1 | Exit0, Docker is ready:29.7.2; healthy fast path did not relaunch |
| Separate later docker info | Still Engine 29.7.2/linux |

This record establishes recovery only. Subsequent PostgreSQL/migration/seed/all 19-test acceptance: [evidence](2026-10-21-postgresql-verification.md).
