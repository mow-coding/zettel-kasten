param(
    [switch]$DryRun,
    [string]$ArchiveRoot = "",
    [string]$InstallRoot = ""
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptRoot "..")).Path
if (-not $ArchiveRoot) {
    $ArchiveRoot = Join-Path $ProjectRoot "archives"
}
if (-not $InstallRoot) {
    $InstallRoot = $ProjectRoot
}

function Resolve-SafeArchiveRoot {
    param([string]$PathValue)
    $fullPath = [System.IO.Path]::GetFullPath($PathValue)
    $trimmed = $fullPath.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    $driveRootRaw = [System.IO.Path]::GetPathRoot($fullPath)
    if ($null -eq $driveRootRaw) {
        $driveRootRaw = ""
    }
    $driveRoot = $driveRootRaw.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    $projectTrimmed = $ProjectRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    if (Test-Path -LiteralPath $fullPath -PathType Leaf) {
        Write-Host "ArchiveRoot must be a directory path, not a file: $fullPath"
        exit 1
    }
    if ($driveRoot -and $trimmed.Equals($driveRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        Write-Host "ArchiveRoot is too broad and must not be a drive root: $fullPath"
        exit 1
    }
    if ($trimmed.Equals($projectTrimmed, [System.StringComparison]::OrdinalIgnoreCase)) {
        Write-Host "ArchiveRoot must not be the repository root: $fullPath"
        exit 1
    }
    $blocked = @($env:SystemRoot, $env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:ProgramData)
    foreach ($item in $blocked) {
        if (-not $item) {
            continue
        }
        $blockedPath = [System.IO.Path]::GetFullPath($item).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
        $blockedPrefix = $blockedPath + [System.IO.Path]::DirectorySeparatorChar
        if (
            $trimmed.Equals($blockedPath, [System.StringComparison]::OrdinalIgnoreCase) -or
            $trimmed.StartsWith($blockedPrefix, [System.StringComparison]::OrdinalIgnoreCase)
        ) {
            Write-Host "ArchiveRoot must not be a system directory: $fullPath"
            exit 1
        }
    }
    return $fullPath
}

$ArchiveRoot = Resolve-SafeArchiveRoot $ArchiveRoot

function Test-CommandExists {
    param([string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-DockerComposeAvailable {
    $PreviousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & docker compose version *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $PreviousPreference
    }
}

function Test-DockerDaemonAvailable {
    $PreviousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & docker info *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $PreviousPreference
    }
}

$DockerInstalled = Test-CommandExists "docker"
$ComposeAvailable = $false
$DockerDaemonAvailable = $false
if ($DockerInstalled) {
    $ComposeAvailable = Test-DockerComposeAvailable
    $DockerDaemonAvailable = Test-DockerDaemonAvailable
}

Write-Host "WOM-kit Docker-first setup"
Write-Host "Project root: $ProjectRoot"
Write-Host "Install root: $InstallRoot"
Write-Host "Archive host root: $ArchiveRoot"
Write-Host "Docker installed: $DockerInstalled"
Write-Host "Docker Compose available: $ComposeAvailable"
Write-Host "Docker daemon available: $DockerDaemonAvailable"
Write-Host ""
Write-Host "Planned steps:"
Write-Host "1. Verify Docker Desktop and Docker Compose."
Write-Host "2. Create the archive host folder if missing."
Write-Host "3. Create .env from .env.example if missing."
Write-Host "4. Build or run the Linux container through docker compose."
Write-Host "5. Start onboarding with: docker compose run --rm archive-cli onboard --dry-run ..."

if ($DryRun) {
    Write-Host ""
    Write-Host "Dry run only. No files or environment settings were changed."
    if (-not $DockerInstalled -or -not $ComposeAvailable) {
        Write-Host "Install Docker Desktop first: https://docs.docker.com/desktop/"
    } elseif (-not $DockerDaemonAvailable) {
        Write-Host "Docker is installed, but the daemon is not reachable. Start Docker Desktop, wait until it is running, then rerun this script."
    }
    exit 0
}

if (-not $DockerInstalled -or -not $ComposeAvailable) {
    Write-Error "Docker Desktop with Docker Compose is required. Install it from https://docs.docker.com/desktop/ and rerun this script."
}
if (-not $DockerDaemonAvailable) {
    Write-Error "Docker is installed, but the daemon is not reachable. Start Docker Desktop, wait until it is running, then rerun this script."
}

New-Item -ItemType Directory -Force -Path $ArchiveRoot | Out-Null

$EnvPath = Join-Path $ProjectRoot ".env"
$EnvExamplePath = Join-Path $ProjectRoot ".env.example"
if (-not (Test-Path $EnvPath)) {
    Copy-Item $EnvExamplePath $EnvPath
    $EscapedArchiveRoot = $ArchiveRoot.Replace("\", "/")
    (Get-Content $EnvPath) -replace "ARCHIVE_HOST_ROOT=./archives", "ARCHIVE_HOST_ROOT=$EscapedArchiveRoot" |
        Set-Content -Encoding UTF8 $EnvPath
}

Write-Host ""
Write-Host "Setup baseline complete."
Write-Host "Next command:"
Write-Host "  docker compose run --rm archive-cli onboard --target-root /archives/personal --type personal --archive-id archive:personal:me --principal-id person:me --principal-name `"Me`" --dry-run"
