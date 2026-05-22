param(
    [switch]$DryRun,
    [switch]$Yes,
    [switch]$ApproveOnboarding,
    [string]$ArchiveRoot = "",
    [ValidateSet("personal", "family", "company")]
    [string]$ArchiveType = "personal",
    [string]$ArchiveId = "",
    [string]$PrincipalId = "",
    [string]$PrincipalName = "",
    [ValidateSet("local_only", "object_storage_planned", "full_provider_plan")]
    [string]$ProviderProfile = "local_only",
    [int]$DockerWaitSeconds = 120
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptRoot "..")).Path
if (-not $ArchiveRoot) {
    $ArchiveRoot = Join-Path $ProjectRoot "archives"
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

function Get-MockDockerState {
    $state = $env:AI_ARCHIVE_TEST_DOCKER_STATE
    if ($state -in @("missing", "compose_missing", "daemon_down", "ready")) {
        return $state
    }
    return ""
}

function Invoke-QuietCommand {
    param([string[]]$Command)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Command[0] @($Command[1..($Command.Length - 1)]) *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $previous
    }
}

function Test-DockerInstalled {
    $mock = Get-MockDockerState
    if ($mock) {
        return $mock -ne "missing"
    }
    return Test-CommandExists "docker"
}

function Test-DockerComposeAvailable {
    $mock = Get-MockDockerState
    if ($mock) {
        return $mock -in @("daemon_down", "ready")
    }
    if (-not (Test-CommandExists "docker")) {
        return $false
    }
    return Invoke-QuietCommand @("docker", "compose", "version")
}

function Test-DockerDaemonAvailable {
    $mock = Get-MockDockerState
    if ($mock) {
        return $mock -eq "ready"
    }
    if (-not (Test-CommandExists "docker")) {
        return $false
    }
    return Invoke-QuietCommand @("docker", "info")
}

function Test-DockerDesktopCliAvailable {
    if (Get-MockDockerState) {
        return $false
    }
    if (-not (Test-CommandExists "docker")) {
        return $false
    }
    return Invoke-QuietCommand @("docker", "desktop", "version")
}

function Start-DockerDesktopIfPossible {
    if (Get-MockDockerState) {
        return
    }
    if (Test-DockerDesktopCliAvailable) {
        Write-Host "Starting Docker Desktop through docker desktop start ..."
        & docker desktop start *> $null
        return
    }
    $desktopPath = Join-Path $env:LOCALAPPDATA "Programs\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $desktopPath) {
        Write-Host "Starting Docker Desktop ..."
        Start-Process -FilePath $desktopPath -WindowStyle Hidden | Out-Null
        return
    }
    Write-Host "Docker Desktop start command was not found. Start Docker Desktop manually if it is installed."
}

function Wait-DockerDaemon {
    param([int]$TimeoutSeconds)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-DockerDaemonAvailable) {
            return $true
        }
        Start-Sleep -Seconds 3
    }
    return $false
}

function Confirm-Action {
    param([string]$Prompt)
    if ($Yes) {
        return $true
    }
    if ([Console]::IsInputRedirected) {
        return $false
    }
    $answer = Read-Host "$Prompt [y/N]"
    return $answer -match "^(y|yes)$"
}

function Read-RequiredValue {
    param(
        [string]$Prompt,
        [string]$Default = ""
    )
    $suffix = ""
    if ($Default) {
        $suffix = " [$Default]"
    }
    $answer = Read-Host "$Prompt$suffix"
    if ($answer) {
        return $answer
    }
    return $Default
}

function Complete-OnboardingValues {
    if (Get-OnboardingReady) {
        return $true
    }
    if ([Console]::IsInputRedirected -or $Yes) {
        Write-Host "Onboarding values are missing. Provide -ArchiveId and -PrincipalId, for example:"
        Write-Host "  -ArchiveId archive:personal:me -PrincipalId person:me -PrincipalName `"Me`""
        return $false
    }
    Write-Host ""
    Write-Host "Archive onboarding needs a few names. Press Enter to accept a suggested value."
    if (-not $ArchiveId) {
        $script:ArchiveId = Read-RequiredValue "Archive id" "archive:personal:me"
    }
    if (-not $PrincipalId) {
        $script:PrincipalId = Read-RequiredValue "Owner/principal id" "person:me"
    }
    if (-not $PrincipalName) {
        $script:PrincipalName = Read-RequiredValue "Display name" "Me"
    }
    return Get-OnboardingReady
}

function Invoke-DockerDesktopInstall {
    if (-not (Test-CommandExists "winget")) {
        Write-Host "WinGet is not available. Install Docker Desktop manually: https://docs.docker.com/desktop/setup/install/windows-install/"
        return $false
    }
    if (-not (Confirm-Action "Docker Desktop is missing. Install it with WinGet now?")) {
        Write-Host "Docker Desktop install skipped. Rerun with -Yes or install it manually from https://docs.docker.com/desktop/setup/install/windows-install/"
        return $false
    }
    Write-Host "Installing Docker Desktop with WinGet. Windows may show package agreement or permission prompts."
    & winget install --id Docker.DockerDesktop -e --source winget
    return $LASTEXITCODE -eq 0
}

function Get-OnboardingReady {
    return $ArchiveId -and $PrincipalId
}

function Build-OnboardArgs {
    param([switch]$Approve)
    $targetInContainer = "/archives/$ArchiveType"
    $args = @(
        "compose", "run", "--rm", "archive-cli", "onboard",
        "--target-root", $targetInContainer,
        "--type", $ArchiveType,
        "--archive-id", $ArchiveId,
        "--principal-id", $PrincipalId,
        "--provider-profile", $ProviderProfile
    )
    if ($PrincipalName) {
        $args += @("--principal-name", $PrincipalName)
    }
    if ($Approve) {
        $args += "--approve"
    } else {
        $args += "--dry-run"
    }
    return $args
}

$DockerInstalled = Test-DockerInstalled
$ComposeAvailable = Test-DockerComposeAvailable
$DockerDaemonAvailable = Test-DockerDaemonAvailable
$OnboardingReady = Get-OnboardingReady
$ShouldApproveOnboarding = $Yes -or $ApproveOnboarding

Write-Host "Zettel-Kasten one-command setup"
Write-Host "Project root: $ProjectRoot"
Write-Host "Archive host root: $ArchiveRoot"
Write-Host "Archive type: $ArchiveType"
Write-Host "Provider profile: $ProviderProfile"
Write-Host "Docker installed: $DockerInstalled"
Write-Host "Docker Compose available: $ComposeAvailable"
Write-Host "Docker daemon available: $DockerDaemonAvailable"
Write-Host "Onboarding values complete: $OnboardingReady"
Write-Host ""
Write-Host "Planned flow:"
Write-Host "1. Check Docker CLI, Docker Compose, and Docker daemon."
Write-Host "2. If Docker Desktop is missing, request approval before installing it."
Write-Host "3. Start Docker Desktop if possible and wait for docker info."
Write-Host "4. Create .env and archive host folder through scripts/install-windows.ps1."
Write-Host "5. Run docker compose config."
Write-Host "6. Run archive-cli doctor inside the Linux container."
Write-Host "7. Run archive onboarding dry-run, then approve only when requested."

if ($DryRun) {
    Write-Host ""
    Write-Host "Dry run only. No files, Docker installs, or archive folders were changed."
    if (-not $DockerInstalled) {
        Write-Host "Docker Desktop would be installed with: winget install --id Docker.DockerDesktop -e --source winget"
    } elseif (-not $ComposeAvailable) {
        Write-Host "Docker Compose is missing. Docker Desktop includes Docker Compose; repair or reinstall Docker Desktop."
    } elseif (-not $DockerDaemonAvailable) {
        Write-Host "Docker Desktop would be started, then this script would wait for docker info."
    }
    if ($OnboardingReady) {
        Write-Host "Onboarding dry-run command:"
        Write-Host "  docker $(Build-OnboardArgs)"
    } else {
        Write-Host "Onboarding needs --archive-id and --principal-id before it can run."
    }
    exit 0
}

if (-not (Complete-OnboardingValues)) {
    exit 1
}
$OnboardingReady = Get-OnboardingReady

if (-not $DockerInstalled) {
    if (-not (Invoke-DockerDesktopInstall)) {
        exit 1
    }
    $DockerInstalled = Test-DockerInstalled
    $ComposeAvailable = Test-DockerComposeAvailable
    $DockerDaemonAvailable = Test-DockerDaemonAvailable
}

if (-not $DockerInstalled -or -not $ComposeAvailable) {
    Write-Error "Docker Desktop with Docker Compose is required. Install it from https://docs.docker.com/desktop/setup/install/windows-install/ and rerun setup."
}

if (-not $DockerDaemonAvailable) {
    Start-DockerDesktopIfPossible
    if (-not (Wait-DockerDaemon -TimeoutSeconds $DockerWaitSeconds)) {
        Write-Error "Docker is installed, but the daemon is not reachable. Start Docker Desktop, accept required prompts, then rerun setup."
    }
}

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ScriptRoot "install-windows.ps1") -ArchiveRoot $ArchiveRoot
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& docker compose config *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker compose config failed."
}

& docker compose run --rm archive-cli doctor examples/fake-life-archive --strict
if ($LASTEXITCODE -ne 0) {
    Write-Error "Container doctor smoke test failed."
}

if (-not $OnboardingReady) {
    Write-Host ""
    Write-Host "Setup baseline complete. To create an archive, rerun with --archive-id and --principal-id."
    exit 0
}

$onboardArgs = Build-OnboardArgs
& docker @onboardArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if ($ShouldApproveOnboarding) {
    $approveArgs = Build-OnboardArgs -Approve
    & docker @approveArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

Write-Host ""
Write-Host "Zettel-Kasten setup complete."
