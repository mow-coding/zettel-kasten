# One-Command Setup

This is the beginner entrypoint for WOM-kit.

The goal is:

```text
one command
-> check Docker
-> install or guide Docker with user approval
-> start Docker
-> prepare archive mount folder and .env
-> run container smoke test
-> preview archive onboarding
```

## Commands

Windows PowerShell:

```powershell
.\scripts\setup-windows.ps1 -DryRun
```

macOS/Linux:

```bash
sh scripts/setup-unix.sh --dry-run
```

In v0.4.0 stop after the dry-run. Real `onboard` is fixed closed before
target/template/provider reads and creates no archive. Do not remove the dry-run
flag expecting archive creation.

Historical non-dry-run setup examples are intentionally omitted in v0.4.0.
Supply onboarding values only to the dry-run if you need a complete preview.

If the script is running in a real interactive terminal and onboarding values are missing, it asks beginner-friendly questions:

```text
Archive id
Owner/principal id
Display name
```

If the script is running non-interactively, such as through an AI tool or CI job, missing onboarding values stop setup before Docker installation, `.env` creation, or archive folder creation.

## Setup vs Install Scripts

```text
setup-windows.ps1 / setup-unix.sh
  Full one-command orchestrator.
  Checks Docker, optionally installs or guides Docker, starts Docker,
  runs compose checks, runs container doctor, and previews onboarding in the
  supported v0.4.0 flow.

install-windows.ps1 / install-unix.sh
  Lower-level baseline step.
  Use after Docker is already ready.
  Creates the archive host folder and .env.
```

## Docker Install Policy

The setup scripts do not silently install Docker.

Windows:

```text
If Docker is missing and WinGet is available,
the script can run:
winget install --id Docker.DockerDesktop -e --source winget
```

macOS:

```text
If Docker is missing and Homebrew is available,
the script can run:
brew install --cask docker
```

Linux:

```text
v1 does not auto-install Docker by distribution.
The script prints Docker Engine/Desktop guidance.
```

## Docker Desktop State

The script distinguishes:

```text
Docker CLI missing
Docker Compose missing
Docker installed but daemon stopped
Docker ready
```

If Docker is installed but stopped, the script tries to start Docker Desktop when the host supports it, then waits for `docker info`.

## Safety

- `--dry-run` writes no files and installs nothing.
- Docker installation requires approval or `--yes`.
- Docker Desktop may still show OS permission, license, WSL, or password prompts.
- Unsafe archive roots such as drive roots, repository root, files, or system directories are rejected.
- The Docker runtime runs as non-root with read-only `/app`, no runtime network, dropped Linux capabilities, and `/archives` as the writable mount.
- Provider secrets are not collected.
- `provider-bindings.yml` stores references only.
- External provider APIs are not mutated.

## References

- Docker Desktop overview: https://docs.docker.com/desktop/
- Docker Desktop for Windows: https://docs.docker.com/desktop/setup/install/windows-install/
- Docker Desktop for Mac: https://docs.docker.com/installation/mac/
- Docker Compose install overview: https://docs.docker.com/compose/install/
- WinGet install command: https://learn.microsoft.com/windows/package-manager/winget/install
