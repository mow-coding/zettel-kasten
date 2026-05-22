# Security Audit 2026-05-21

This is a local pre-release security audit note, not a formal penetration test.

## Scope

Reviewed areas:

- Docker runtime hardening
- Docker build context
- container dependency supply chain
- setup script archive-root guardrails
- archive symlink/path traversal behavior
- MCP path boundaries
- secret-like file/value handling

## Findings And Fixes

### Fixed: Docker Build Context Could Include Ignored Secrets

`.gitignore` protected secret-like files, but `.dockerignore` did not mirror all of those patterns.

Impact:

```text
A file ignored by git could still be sent to Docker build context.
```

Fix:

```text
Added secret/profile/keyring/private-key patterns to .dockerignore.
```

### Fixed: Archive Symlink Escape

Archive scans used safe archive-relative path helpers in many places, but some glob-based reads could encounter a symlink inside the archive that resolved outside the archive root.

Impact:

```text
Host-native CLI/MCP could read or write outside the intended archive root if an archive contained malicious symlinks.
```

Fix:

```text
Added path-within-root checks before service reads/writes and doctor scans.
Doctor now reports archive_symlink_escapes_root.
Service listing/indexing skips unsafe symlink targets.
Write paths such as inbox/, db/archive-index.sqlite, workpacks/, archive.yml, archive-identity.yml, and provider-bindings.yml now resolve through archive-internal path guards.
```

### Fixed: Container MCP Could Address Non-Archive Paths

The Docker runtime protected the filesystem broadly, but MCP still accepted arbitrary absolute paths inside the container.

Impact:

```text
Containerized MCP could inspect /app examples or other container paths if asked.
```

Fix:

```text
Added AI_ARCHIVE_MCP_ALLOWED_ROOTS=/archives to Compose.
MCP path arguments are rejected outside the allowlist.
```

### Fixed: Python Packaging CVEs In Container Image

Docker Scout initially reported:

```text
1 HIGH in vendored wheel 0.45.1 under setuptools 80.9.0
multiple MEDIUM/LOW findings in pip 25.0.1
```

Fix:

```text
Updated hash-locked container dependencies:
pip==26.1.1
setuptools==82.0.1
PyYAML==6.0.3
```

Result after rebuild and rescan:

```text
0 critical
0 high
1 medium
22 low
```

The remaining findings are Debian base-image packages reported by Docker Scout with no fixed package version available in the current `python:3.12-slim` line at scan time.

## Verification

Commands run:

```text
python -m unittest discover -s tests
python cli/archive.py doctor examples/fake-life-archive --strict
docker compose config
docker compose build --no-cache archive-cli
docker compose run --rm archive-cli doctor examples/fake-life-archive --strict
docker scout cves zettel-kasten-archive-kit:local
docker scout quickview zettel-kasten-archive-kit:local
docker scout recommendations zettel-kasten-archive-kit:local
```

Additional MCP boundary check:

```text
archive_doctor /app/examples/fake-life-archive through containerized MCP was rejected.
archive_doctor /archives through containerized MCP passed when the fake archive was mounted there.
```

## Residual Risk

- This is still not a formal external security audit.
- Docker Desktop remains a trusted local dependency.
- The default image still has 1 medium and 22 low base-image CVEs according to Docker Scout.
- Docker Scout recommends considering newer Python runtime lines such as 3.13/3.14 or Alpine for fewer findings, but the project currently stays on Python 3.12 slim for compatibility.
- Future live provider import or provider mutation must use explicit network-enabled services/profiles.

