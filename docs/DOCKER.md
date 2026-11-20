# Docker Runner

The image contains the dependency-free engine and nothing else. It runs the deterministic steps of a review in isolation: `discover`, `questions`, `intake`, `state`, `validate`, `score`.

## What it does not do

- It does not run Claude. The 23-expert review is driven by Claude Code (or the Claude apps) on your machine; there is no tested AI workflow inside the container, and none is claimed.
- It does not run your project's tests. The image has no node, go, java or other toolchains, and the container has no network. Run those checks natively through `EE evidence run`, or in an image built for your stack.

## Use

```bash
mkdir -p reports
PROJECT_DIR=/path/to/project docker compose run --rm audit            # discover -> ./reports
docker compose run --rm audit questions --review /reports
docker compose run --rm audit score --review /reports
```

`PROJECT_DIR` defaults to the current directory, `REPORTS_DIR` to `./reports`.

The container runs as user 10001. On Linux, make the reports folder writable for it, or run as yourself:

```bash
AUDIT_UID=$(id -u) AUDIT_GID=$(id -g) PROJECT_DIR=/path/to/project docker compose run --rm audit
```

Build without Compose: `docker build -f docker/Dockerfile -t enterprise-experts:0.5.1 .`

## Isolation

| Setting | Value |
|---|---|
| Project mount | read-only (`/project:ro`) |
| Writable paths | `/reports` and a 64 MB `/tmp` only; the image filesystem is read-only |
| User | non-root (10001) |
| Network | none |
| Capabilities | all dropped, `no-new-privileges` |
| Limits | 1 CPU, 512 MB memory, 128 processes |
| Docker socket | not mounted |
| Secrets | none in the image; none needed |

`tools/docker_smoke.sh` builds the image and checks these properties (unprivileged user, cannot write to the project or the image, no network, no capabilities, no secret in the output). CI runs it on every pull request.

Tested on Linux with Docker 29 and Compose v5. Not yet tested on macOS or Windows/WSL2. The base image is referenced by tag (`python:3.13-slim`), not by digest; Dependabot proposes updates.
