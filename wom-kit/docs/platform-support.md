# Platform Support

WOM-kit is Docker-first hybrid for non-programmer users.

The host computer may be Windows, macOS, or Linux. The default runtime is a Linux container managed by Docker Compose. This keeps the archive server, CLI, MCP server, SQLite behavior, and future worker/server pieces consistent across a mixed team.

## Support Priority

```text
1. Docker-first runtime for Windows, macOS, and Linux hosts.
2. Shared Python core remains portable for developer/backup host-native use.
3. OS-specific behavior stays in small bootstrap scripts, not product forks.
```

## Runtime Model

```text
host OS
  Windows, macOS, or Linux

Docker runtime
  Linux container

mounted archive data
  host folder -> /archives

runtime hardening
  non-root user
  read-only root filesystem
  no runtime network
  dropped Linux capabilities
```

Default host mount:

```text
ARCHIVE_HOST_ROOT=./archives
```

Container path:

```text
/archives
```

## Path Rules

Archive-internal paths are stable POSIX-style relative paths:

```text
inbox/zet_example.md
objects/manifests/files.jsonl
views/homebase.yml
```

External host paths may use the host OS style in `.env` or bootstrap arguments:

```text
C:\Users\example\Archives
/Users/example/Archives
/home/example/Archives
```

Paths returned by CLI JSON and MCP tools should use archive-relative `/` paths so tests, workpacks, receipts, and AI tool results remain stable.

Unsafe archive-relative paths must be rejected:

```text
../archive.yml
inbox/../archive.yml
C:\Users\example\secret.txt
/home/example/secret.txt
\\server\share\secret.txt
```

## Commands

One-command setup:

Windows:

```powershell
.\scripts\setup-windows.ps1 -DryRun
```

macOS/Linux:

```bash
sh scripts/setup-unix.sh --dry-run
```

Docker-first lower-level commands:

```bash
docker compose run --rm archive-cli doctor examples/fake-life-archive --strict
docker compose run --rm archive-cli onboard --target-root /archives/personal --type personal --archive-id archive:personal:me --principal-id person:me --dry-run
docker compose run --rm archive-mcp
```

Host-native developer fallback from inside `wom-kit/`:

Windows PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m wom_kit.archive_cli doctor examples\fake-life-archive --strict
```

macOS/Linux shell:

```bash
PYTHONPATH=src python -m wom_kit.archive_cli doctor examples/fake-life-archive --strict
```

## Current Boundary

This project now provides Docker Compose runtime files and bootstrap dry-runs. It does not yet provide:

```text
signed native installers
native desktop apps
automatic OS keychain/KeePassXC reads
external provider API mutation
production background daemons
```

## Local Profiles And Secrets

The first keyring/profile baseline is OS-independent.

Local-only profile files should live in ignored paths:

```text
profiles/local/
profiles/*.local.yml
keyrings/local/
keyrings/*.local.yml
.archive-local/
```

These files may list required environment variable names. They should not contain actual tokens, passwords, API keys, or private key material.

`archive doctor` warns when ignore protection is incomplete and fails when it finds obvious secret-like files or values.

## Docker Desktop State

The bootstrap distinguishes these states:

```text
Docker is not installed.
Docker Compose is not available.
Docker is installed, but Docker Desktop is not running.
Docker is installed and the daemon is reachable.
```

The first three states should produce friendly guidance instead of a confusing stack trace.

## Docker Installation Policy

The setup scripts can guide or start Docker installation, but they do not treat Docker Desktop as an invisible dependency.

```text
Windows
  Use WinGet for Docker Desktop when available and approved.

macOS
  Use Homebrew cask for Docker Desktop when available and approved.

Linux
  Print official Docker Engine/Desktop guidance in v1.
```

Docker Desktop may require license, OS permission, password, WSL, or first-run prompts outside the script.

## Container Security Baseline

Default Compose services use:

```text
read_only: true
tmpfs: /tmp
cap_drop: ALL
security_opt: no-new-privileges:true
network_mode: none
user: non-root uid/gid
```

`/archives` remains writable because that is the mounted archive data. Future provider API mutation must use a separate opt-in network-enabled profile rather than opening the default runtime.
