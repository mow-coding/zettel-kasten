#!/usr/bin/env sh
set -eu

DRY_RUN=0
ARCHIVE_ROOT=""
INSTALL_ROOT=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --archive-root)
      ARCHIVE_ROOT="${2:-}"
      shift 2
      ;;
    --install-root)
      INSTALL_ROOT="${2:-}"
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
if [ -z "$INSTALL_ROOT" ]; then
  INSTALL_ROOT="$PROJECT_ROOT"
fi

archive_root_abs() {
  case "$1" in
    /*)
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
  if [ "$trimmed" = "$project_trimmed" ]; then
    echo "Archive root must not be the repository root: $candidate" >&2
    exit 1
  fi
  printf '%s\n' "$candidate"
}

ARCHIVE_ROOT=$(validate_archive_root "$ARCHIVE_ROOT")

if command -v docker >/dev/null 2>&1; then
  DOCKER_INSTALLED=1
else
  DOCKER_INSTALLED=0
fi

if [ "$DOCKER_INSTALLED" -eq 1 ] && docker compose version >/dev/null 2>&1; then
  COMPOSE_AVAILABLE=1
else
  COMPOSE_AVAILABLE=0
fi

if [ "$DOCKER_INSTALLED" -eq 1 ] && docker info >/dev/null 2>&1; then
  DOCKER_DAEMON_AVAILABLE=1
else
  DOCKER_DAEMON_AVAILABLE=0
fi

echo "WOM-kit Docker-first setup"
echo "Project root: $PROJECT_ROOT"
echo "Install root: $INSTALL_ROOT"
echo "Archive host root: $ARCHIVE_ROOT"
echo "Docker installed: $DOCKER_INSTALLED"
echo "Docker Compose available: $COMPOSE_AVAILABLE"
echo "Docker daemon available: $DOCKER_DAEMON_AVAILABLE"
echo ""
echo "Planned steps:"
echo "1. Verify Docker Desktop and Docker Compose."
echo "2. Create the archive host folder if missing."
echo "3. Create .env from .env.example if missing."
echo "4. Build or run the Linux container through docker compose."
echo "5. Start onboarding with: docker compose run --rm archive-cli onboard --dry-run ..."

if [ "$DRY_RUN" -eq 1 ]; then
  echo ""
  echo "Dry run only. No files or environment settings were changed."
  if [ "$DOCKER_INSTALLED" -ne 1 ] || [ "$COMPOSE_AVAILABLE" -ne 1 ]; then
    echo "Install Docker Desktop first: https://docs.docker.com/desktop/"
  elif [ "$DOCKER_DAEMON_AVAILABLE" -ne 1 ]; then
    echo "Docker is installed, but the daemon is not reachable. Start Docker Desktop, wait until it is running, then rerun this script."
  fi
  exit 0
fi

if [ "$DOCKER_INSTALLED" -ne 1 ] || [ "$COMPOSE_AVAILABLE" -ne 1 ]; then
  echo "Docker Desktop with Docker Compose is required. Install it from https://docs.docker.com/desktop/ and rerun this script." >&2
  exit 1
fi

if [ "$DOCKER_DAEMON_AVAILABLE" -ne 1 ]; then
  echo "Docker is installed, but the daemon is not reachable. Start Docker Desktop, wait until it is running, then rerun this script." >&2
  exit 1
fi

mkdir -p "$ARCHIVE_ROOT"

if [ ! -f "$PROJECT_ROOT/.env" ]; then
  cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
  ARCHIVE_ROOT_ESCAPED=$(printf '%s\n' "$ARCHIVE_ROOT" | sed 's/[\/&]/\\&/g')
  HOST_UID=$(id -u 2>/dev/null || printf '10001')
  HOST_GID=$(id -g 2>/dev/null || printf '10001')
  sed \
    -e "s/ARCHIVE_HOST_ROOT=.\\/archives/ARCHIVE_HOST_ROOT=$ARCHIVE_ROOT_ESCAPED/" \
    -e "s/ARCHIVE_UID=10001/ARCHIVE_UID=$HOST_UID/" \
    -e "s/ARCHIVE_GID=10001/ARCHIVE_GID=$HOST_GID/" \
    "$PROJECT_ROOT/.env" > "$PROJECT_ROOT/.env.tmp"
  mv "$PROJECT_ROOT/.env.tmp" "$PROJECT_ROOT/.env"
fi

echo ""
echo "Setup baseline complete."
echo "Next command:"
echo "  docker compose run --rm archive-cli onboard --target-root /archives/personal --type personal --archive-id archive:personal:me --principal-id person:me --principal-name \"Me\" --dry-run"
