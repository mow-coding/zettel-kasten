# Security Hardening

This document records the local installer and container security baseline.

AI Archive Kit is still a local-first developer-stage toolkit, not a completed audited product. This hardening reduces obvious local blast radius before broader release.

## Runtime Model

The default Docker Compose runtime is intentionally narrow:

```text
host archive folder -> /archives
container app code -> /app
network -> disabled
runtime user -> non-root
container root filesystem -> read-only
temporary writes -> /tmp tmpfs
```

The only expected writable path in the container is `/archives`.

## Docker Hardening

The Compose services use:

```text
user: non-root uid/gid
read_only: true
tmpfs: /tmp
cap_drop: ALL
security_opt: no-new-privileges:true
network_mode: none
```

The Docker socket is not mounted. Host networking and privileged mode are not used.

Why this matters:

- If a CLI/MCP bug writes outside the archive, `/app` should be read-only.
- If code execution is compromised, the container has no default outbound network.
- If a process tries to gain Linux capabilities, they are dropped by default.
- If the archive needs durable writes, those writes must be explicit through `/archives`.

## Supply Chain Baseline

The container image pins:

```text
python:3.12-slim@sha256:...
```

Container Python dependencies are installed from `requirements-container.txt` with `--require-hashes`.

The container lock currently pins `pip`, `setuptools`, and `PyYAML`. This is intentional: even packaging tools that are mainly used at build time can remain present in the final image and show up in CVE scans.

The local package is installed with:

```text
--no-build-isolation --no-deps -e .
```

This keeps container dependency resolution explicit. Host-native developer installs remain a developer path and are not treated as the release security baseline.

## Installer Guardrails

The setup scripts reject archive roots that are too broad:

```text
drive root or filesystem root
repository root
common system directories
file paths
```

Dry-run mode writes no files, installs nothing, and does not create archive folders.

Docker installation and first-run prompts remain user-controlled:

```text
Windows: WinGet can install Docker Desktop after approval.
macOS: Homebrew can install Docker Desktop after approval.
Linux: v1 prints official Docker Engine/Desktop guidance.
```

## Secrets Boundary

The setup scripts do not collect provider secrets.

`provider-bindings.yml` should contain only:

```text
provider names
bucket/repo/project names
environment variable names
KeePassXC or keyring references
manual change plans
```

It must not contain actual tokens, passwords, private keys, or database URLs.

`archive doctor --strict` scans common secret-like files and values.

## MCP Boundary

MCP stays local stdio.

In the Docker Compose runtime, MCP paths are allowlisted to `/archives` through:

```text
AI_ARCHIVE_MCP_ALLOWED_ROOTS=/archives
```

That means a containerized MCP call should not be able to inspect or mutate `/app`, `/tmp`, or other container paths even though the CLI service can still run built-in examples for smoke tests.

MCP can:

```text
inspect
search
create inbox drafts
plan onboarding
plan real pilot preflight
preview minting/share/ownership transfer
```

MCP must not:

```text
apply real pilot setup
apply onboarding
mint canonical memory
apply ownership transfer
mutate external provider accounts
store provider secrets
```

## Real Data Preflight

Before connecting real personal or team data, run:

```powershell
python cli\archive.py preflight <archive> --strict --check-docker
python cli\archive.py restore-drill <archive> --target C:\tmp\archive-restore --dry-run
```

This catches the most dangerous first-pilot mistakes:

```text
drive root or filesystem root as a source
whole home folder as a source
system directories
Archive Kit repository root as a source
source root that contains the archive itself
overlapping personal/team archive roots
doctor errors and optional Docker runtime failure
missing restore drill receipt when --require-restore-drill is used
```

Restore drill copies the archive control plane to a clean target, runs strict doctor, rebuilds the SQLite index, performs a basic search smoke test, and writes a recovery receipt. It does not copy external originals from PC folders, SSDs, SaaS providers, or object storage.

## Remaining Risks

This is not a formal penetration test.

Known remaining risks:

- A user can still mount a sensitive host folder into `/archives`; setup guards reduce this but cannot reason about every custom path.
- Docker Desktop itself is a trusted local dependency.
- The Docker build stage still needs network access to download the pinned base image and hashed wheels unless a local cache is available.
- Docker Scout still reports residual Debian base-image CVEs with no fixed package version available in the current 3.12 slim image: 1 medium and 22 low at the time of the 2026-05-21 scan.
- Future provider API mutation will need a separate opt-in network-enabled service/profile.
- OS keychain and KeePassXC integration is still not implemented.
- Restore drill verifies the archive control plane, not full recovery of every external original object.

## Deep Audit Follow-Up

The 2026-05-21 deep audit added three extra protections beyond the initial hardening pass:

```text
Docker build context ignores secret-like files.
Archive symlink escapes are rejected or skipped before reads/writes.
Containerized MCP is path-jail-limited to /archives.
```

Docker Scout initially found 1 high and several medium Python packaging CVEs in the image. Updating the hash-locked container dependencies to `pip==26.1.1` and `setuptools==82.0.1` removed those Python packaging findings. The remaining findings are base-image OS packages without fixed versions in the current 3.12 slim line.

## References

- Docker Engine security: https://docs.docker.com/engine/security/
- Docker Compose services reference: https://docs.docker.com/reference/compose-file/services/
- Docker Compose trust model: https://docs.docker.com/compose/trust-model/
- Docker rootless mode: https://docs.docker.com/engine/security/rootless/
- Docker Scout: https://docs.docker.com/scout/
- Docker Scout CVE command: https://docs.docker.com/reference/cli/docker/scout/cves/
- pip secure installs: https://pip.pypa.io/en/stable/topics/secure-installs/
