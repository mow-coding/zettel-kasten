# Docker-First Bootstrap

WOM-kit uses a Docker-first hybrid setup for non-programmer users.

The user's computer can be Windows, macOS, or Linux. The WOM-kit runtime runs inside a Linux container so the CLI, MCP server, SQLite behavior, and future server pieces behave the same way across the team.

## User-Facing Flow

```text
1. Run the WOM-kit setup script.
2. Let the script check Docker.
3. Approve Docker installation or follow official guidance if Docker is missing.
4. Let the script prepare the archive mount and run container checks.
5. Ask AI to plan onboarding or pass onboarding values directly.
6. Keep provider secrets in KeePassXC, an OS keychain, or environment injection.
```

Windows:

```powershell
.\scripts\setup-windows.ps1 -DryRun
```

macOS/Linux:

```bash
sh scripts/setup-unix.sh --dry-run
```

After the dry-run looks right, rerun without the dry-run flag.

The lower-level `install-windows.ps1` and `install-unix.sh` scripts still exist. They are used after Docker is already ready, and only prepare `.env` plus the archive host folder.

When setup runs in a real interactive terminal and onboarding values are missing, it asks for them. When setup runs non-interactively, such as from an AI tool, missing onboarding values stop setup before it changes files or starts installation.

The bootstrap checks three separate Docker facts:

```text
Docker CLI is installed.
Docker Compose is available.
Docker Desktop daemon is running.
```

If Docker is installed but the daemon is not reachable, start Docker Desktop and wait until it finishes starting.

The higher-level setup scripts also try to start Docker Desktop when supported:

```text
docker desktop start
Windows Docker Desktop executable
macOS open -a Docker
```

## Docker Runtime

The runtime is defined by:

```text
Dockerfile
compose.yaml
.env.example
```

Default services:

```text
archive-cli
archive-mcp
```

The host archive folder is mounted into the container as:

```text
/archives
```

The default host folder is:

```text
./archives
```

Override it in `.env`:

```text
ARCHIVE_HOST_ROOT=D:/Archives
```

## Onboarding

Preview a personal archive:

```bash
docker compose run --rm archive-cli onboard \
  --target-root /archives/personal \
  --type personal \
  --archive-id archive:personal:me \
  --principal-id person:me \
  --principal-name "Me" \
  --dry-run
```

Apply after review:

```bash
docker compose run --rm archive-cli onboard \
  --target-root /archives/personal \
  --type personal \
  --archive-id archive:personal:me \
  --principal-id person:me \
  --principal-name "Me" \
  --approve
```

## Provider Profiles

```text
local_only
  external_ssd and keepassxc references only.

object_storage_planned
  R2/B2, rclone, restic, external SSD, and keyring references.

full_provider_plan
  GitHub, R2/B2, optional Neon coordination, backup tooling, and keyring references.
```

Provider profiles never store real secrets. They only write env var names, role names, bucket names, repo names, and keyring entry references.

## AI/MCP Boundary

MCP exposes `archive_onboarding_plan` as check-only. AI can help plan setup, explain blockers, and prepare commands, but MCP does not create archive folders or mutate external provider accounts.

Real archive creation is CLI-only through:

```text
archive onboard --approve
```

## Docker Desktop Note

Docker Desktop is the easiest path for Windows and Mac. It is free for personal use, education, non-commercial open source, and small businesses under Docker's published limits, but larger organizations should review Docker Desktop licensing before company-wide use.
