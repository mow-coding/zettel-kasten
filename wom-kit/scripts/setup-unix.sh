#!/usr/bin/env sh
set -eu

DRY_RUN=0
YES=0
APPROVE_ONBOARDING=0
ARCHIVE_ROOT=""
ARCHIVE_TYPE="personal"
ARCHIVE_ID=""
PRINCIPAL_ID=""
PRINCIPAL_NAME=""
PROVIDER_PROFILE="local_only"
DOCKER_WAIT_SECONDS=120

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --yes)
      YES=1
      shift
      ;;
    --approve-onboarding)
      APPROVE_ONBOARDING=1
      shift
      ;;
    --archive-root)
      ARCHIVE_ROOT="${2:-}"
      shift 2
      ;;
    --type)
      ARCHIVE_TYPE="${2:-}"
      shift 2
      ;;
    --archive-id)
      ARCHIVE_ID="${2:-}"
      shift 2
      ;;
    --principal-id)
      PRINCIPAL_ID="${2:-}"
      shift 2
      ;;
    --principal-name)
      PRINCIPAL_NAME="${2:-}"
      shift 2
      ;;
    --provider-profile)
      PROVIDER_PROFILE="${2:-}"
      shift 2
      ;;
    --docker-wait-seconds)
      DOCKER_WAIT_SECONDS="${2:-120}"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

if [ -z "$ARCHIVE_ROOT" ]; then
  ARCHIVE_ROOT="$PROJECT_ROOT/archives"
fi

archive_root_abs() {
  case "$1" in
    /*|[A-Za-z]:/*|[A-Za-z]:\\*)
      printf '%s\n' "$1"
      ;;
    *)
      printf '%s/%s\n' "$PWD" "$1"
      ;;
  esac
}

validate_archive_root() {
  candidate=$(archive_root_abs "$1")
  trimmed=$(printf '%s\n' "$candidate" | sed 's:/*$::')
  [ -n "$trimmed" ] || trimmed="/"
  if [ -f "$candidate" ]; then
    echo "Archive root must be a directory path, not a file: $candidate" >&2
    exit 1
  fi
  case "$trimmed" in
    /|/home|/Users|/root|/tmp|/var|/etc|/opt|/usr|/bin|/sbin|/mnt|/media)
      echo "Archive root is too broad or system-owned: $candidate" >&2
      exit 1
      ;;
  esac
  case "$trimmed" in
    /root/*|/tmp/*|/var/*|/etc/*|/opt/*|/usr/*|/bin/*|/sbin/*)
      echo "Archive root must not live under a system-owned directory: $candidate" >&2
      exit 1
      ;;
  esac
  project_trimmed=$(printf '%s\n' "$PROJECT_ROOT" | sed 's:/*$::')
  # Canonicalize the candidate when it exists so equivalent paths in different
  # forms (e.g. C:/x vs /c/x under git-bash, symlinks, trailing slashes, ..)
  # are caught by the repository-root guard. This only ever adds rejections.
  candidate_canon="$trimmed"
  if [ -d "$candidate" ]; then
    canon=$(CDPATH= cd -- "$candidate" 2>/dev/null && pwd) \
      && candidate_canon=$(printf '%s\n' "$canon" | sed 's:/*$::')
  fi
  if [ "$trimmed" = "$project_trimmed" ] || [ "$candidate_canon" = "$project_trimmed" ]; then
    echo "Archive root must not be the repository root: $candidate" >&2
    exit 1
  fi
  printf '%s\n' "$candidate"
}

ARCHIVE_ROOT=$(validate_archive_root "$ARCHIVE_ROOT")

OS_NAME=$(uname -s 2>/dev/null || echo unknown)

mock_state() {
  case "${AI_ARCHIVE_TEST_DOCKER_STATE:-}" in
    missing|compose_missing|daemon_down|ready)
      printf '%s\n' "$AI_ARCHIVE_TEST_DOCKER_STATE"
      ;;
    *)
      printf '\n'
      ;;
  esac
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

docker_installed() {
  state=$(mock_state)
  if [ -n "$state" ]; then
    [ "$state" != "missing" ]
    return
  fi
  command_exists docker
}

docker_compose_available() {
  state=$(mock_state)
  if [ -n "$state" ]; then
    [ "$state" = "daemon_down" ] || [ "$state" = "ready" ]
    return
  fi
  command_exists docker && docker compose version >/dev/null 2>&1
}

docker_daemon_available() {
  state=$(mock_state)
  if [ -n "$state" ]; then
    [ "$state" = "ready" ]
    return
  fi
  command_exists docker && docker info >/dev/null 2>&1
}

docker_desktop_cli_available() {
  [ -z "$(mock_state)" ] && command_exists docker && docker desktop version >/dev/null 2>&1
}

prompt_yes() {
  prompt="$1"
  if [ "$YES" -eq 1 ]; then
    return 0
  fi
  if [ ! -t 0 ]; then
    return 1
  fi
  printf '%s [y/N] ' "$prompt"
  read answer
  case "$answer" in
    y|Y|yes|YES)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

read_required_value() {
  prompt="$1"
  default="$2"
  if [ -n "$default" ]; then
    printf '%s [%s] ' "$prompt" "$default"
  else
    printf '%s ' "$prompt"
  fi
  read answer
  if [ -n "$answer" ]; then
    printf '%s\n' "$answer"
  else
    printf '%s\n' "$default"
  fi
}

complete_onboarding_values() {
  if onboarding_ready; then
    return 0
  fi
  if [ ! -t 0 ] || [ "$YES" -eq 1 ]; then
    echo "Onboarding values are missing. Provide --archive-id and --principal-id, for example:" >&2
    echo "  --archive-id archive:personal:me --principal-id person:me --principal-name \"Me\"" >&2
    return 1
  fi
  echo ""
  echo "Archive onboarding needs a few names. Press Enter to accept a suggested value."
  if [ -z "$ARCHIVE_ID" ]; then
    ARCHIVE_ID=$(read_required_value "Archive id" "archive:personal:me")
  fi
  if [ -z "$PRINCIPAL_ID" ]; then
    PRINCIPAL_ID=$(read_required_value "Owner/principal id" "person:me")
  fi
  if [ -z "$PRINCIPAL_NAME" ]; then
    PRINCIPAL_NAME=$(read_required_value "Display name" "Me")
  fi
  onboarding_ready
}

install_docker_if_possible() {
  case "$OS_NAME" in
    Darwin)
      if ! command_exists brew; then
        echo "Homebrew is not available. Install Docker Desktop manually: https://docs.docker.com/installation/mac/" >&2
        return 1
      fi
      if ! prompt_yes "Docker Desktop is missing. Install it with Homebrew now?"; then
        echo "Docker Desktop install skipped. Rerun with --yes or install it manually from https://docs.docker.com/installation/mac/" >&2
        return 1
      fi
      echo "Installing Docker Desktop with Homebrew. macOS may ask for permissions on first run."
      brew install --cask docker
      ;;
    Linux)
      echo "Docker is missing. Linux automatic Docker installation is not enabled in v1." >&2
      echo "Install Docker Engine/Desktop from https://docs.docker.com/desktop/ or https://docs.docker.com/engine/install/" >&2
      return 1
      ;;
    *)
      echo "Unsupported Unix platform: $OS_NAME. Install Docker manually from https://docs.docker.com/desktop/" >&2
      return 1
      ;;
  esac
}

start_docker_if_possible() {
  if [ -n "$(mock_state)" ]; then
    return 0
  fi
  if docker_desktop_cli_available; then
    echo "Starting Docker Desktop through docker desktop start ..."
    docker desktop start >/dev/null 2>&1 || true
    return 0
  fi
  if [ "$OS_NAME" = "Darwin" ] && command_exists open; then
    echo "Starting Docker Desktop ..."
    open -a Docker >/dev/null 2>&1 || true
    return 0
  fi
  echo "Docker Desktop start command was not found. Start Docker manually if it is installed."
}

wait_for_docker() {
  timeout="$1"
  start=$(date +%s)
  while :; do
    if docker_daemon_available; then
      return 0
    fi
    now=$(date +%s)
    elapsed=$((now - start))
    if [ "$elapsed" -ge "$timeout" ]; then
      return 1
    fi
    sleep 3
  done
}

onboarding_ready() {
  [ -n "$ARCHIVE_ID" ] && [ -n "$PRINCIPAL_ID" ]
}

print_onboard_command() {
  mode="$1"
  printf '  docker compose run --rm archive-cli onboard --target-root /archives/%s --type %s --archive-id %s --principal-id %s --provider-profile %s' "$ARCHIVE_TYPE" "$ARCHIVE_TYPE" "$ARCHIVE_ID" "$PRINCIPAL_ID" "$PROVIDER_PROFILE"
  if [ -n "$PRINCIPAL_NAME" ]; then
    printf ' --principal-name "%s"' "$PRINCIPAL_NAME"
  fi
  if [ "$mode" = "approve" ]; then
    printf ' --approve\n'
  else
    printf ' --dry-run\n'
  fi
}

run_onboarding() {
  mode="$1"
  set -- compose run --rm archive-cli onboard \
    --target-root "/archives/$ARCHIVE_TYPE" \
    --type "$ARCHIVE_TYPE" \
    --archive-id "$ARCHIVE_ID" \
    --principal-id "$PRINCIPAL_ID" \
    --provider-profile "$PROVIDER_PROFILE"
  if [ -n "$PRINCIPAL_NAME" ]; then
    set -- "$@" --principal-name "$PRINCIPAL_NAME"
  fi
  if [ "$mode" = "approve" ]; then
    set -- "$@" --approve
  else
    set -- "$@" --dry-run
  fi
  docker "$@"
}

if docker_installed; then
  DOCKER_INSTALLED=1
else
  DOCKER_INSTALLED=0
fi
if docker_compose_available; then
  COMPOSE_AVAILABLE=1
else
  COMPOSE_AVAILABLE=0
fi
if docker_daemon_available; then
  DOCKER_DAEMON_AVAILABLE=1
else
  DOCKER_DAEMON_AVAILABLE=0
fi
if onboarding_ready; then
  ONBOARDING_READY=1
else
  ONBOARDING_READY=0
fi

echo "Zettel-Kasten one-command setup"
echo "Project root: $PROJECT_ROOT"
echo "Archive host root: $ARCHIVE_ROOT"
echo "Host OS: $OS_NAME"
echo "Archive type: $ARCHIVE_TYPE"
echo "Provider profile: $PROVIDER_PROFILE"
echo "Docker installed: $DOCKER_INSTALLED"
echo "Docker Compose available: $COMPOSE_AVAILABLE"
echo "Docker daemon available: $DOCKER_DAEMON_AVAILABLE"
echo "Onboarding values complete: $ONBOARDING_READY"
echo ""
echo "Planned flow:"
echo "1. Check Docker CLI, Docker Compose, and Docker daemon."
echo "2. If Docker is missing, request approval before installing or print official guidance."
echo "3. Start Docker Desktop/Engine if possible and wait for docker info."
echo "4. Create .env and archive host folder through scripts/install-unix.sh."
echo "5. Run docker compose config."
echo "6. Run archive-cli doctor inside the Linux container."
echo "7. Run archive onboarding dry-run, then approve only when requested."

if [ "$DRY_RUN" -eq 1 ]; then
  echo ""
  echo "Dry run only. No files, Docker installs, or archive folders were changed."
  if [ "$DOCKER_INSTALLED" -ne 1 ]; then
    if [ "$OS_NAME" = "Darwin" ]; then
      echo "Docker Desktop would be installed with: brew install --cask docker"
    else
      echo "Docker install guidance would be shown from https://docs.docker.com/desktop/"
    fi
  elif [ "$COMPOSE_AVAILABLE" -ne 1 ]; then
    echo "Docker Compose is missing. Docker Desktop includes Compose; Linux users may need the Compose plugin."
  elif [ "$DOCKER_DAEMON_AVAILABLE" -ne 1 ]; then
    echo "Docker would be started if possible, then this script would wait for docker info."
  fi
  if [ "$ONBOARDING_READY" -eq 1 ]; then
    echo "Onboarding dry-run command:"
    print_onboard_command dry-run
  else
    echo "Onboarding needs --archive-id and --principal-id before it can run."
  fi
  exit 0
fi

complete_onboarding_values || exit 1
ONBOARDING_READY=1

if [ "$DOCKER_INSTALLED" -ne 1 ]; then
  install_docker_if_possible || exit 1
fi

if ! docker_compose_available; then
  echo "Docker Compose is required. Docker Desktop includes Compose; Linux users may need the Compose plugin." >&2
  exit 1
fi

if ! docker_daemon_available; then
  start_docker_if_possible
  if ! wait_for_docker "$DOCKER_WAIT_SECONDS"; then
    echo "Docker is installed, but the daemon is not reachable. Start Docker Desktop/Engine, accept required prompts, then rerun setup." >&2
    exit 1
  fi
fi

sh "$SCRIPT_DIR/install-unix.sh" --archive-root "$ARCHIVE_ROOT"

docker compose config >/dev/null
docker compose run --rm archive-cli doctor examples/fake-life-archive --strict

if [ "$ONBOARDING_READY" -ne 1 ]; then
  echo ""
  echo "Setup baseline complete. To create an archive, rerun with --archive-id and --principal-id."
  exit 0
fi

run_onboarding dry-run

if [ "$YES" -eq 1 ] || [ "$APPROVE_ONBOARDING" -eq 1 ]; then
  run_onboarding approve
fi

echo ""
echo "Zettel-Kasten setup complete."
