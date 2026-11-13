#!/usr/bin/env bash
# Ubuntu: install missing tools/dependencies and start both development servers.
set -Eeuo pipefail

fail() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }
info() { printf '[INFO] %s\n' "$*"; }
trap 'printf "[ERROR] Startup failed at line %s. Check the output above.\n" "$LINENO" >&2' ERR

install=false
case "${1:-}" in
  --install) install=true ;;
  --help|-h)
    printf 'Usage: bash scripts/start-dev.sh [--install]\n'
    printf 'Missing tools and dependencies are installed automatically. Ubuntu packages may need sudo.\n'
    printf '%s\n' '--install forces project dependency installation.'
    exit 0
    ;;
  '') ;;
  *) fail "Unknown argument: $1. Use --help." ;;
esac
(( $# <= 1 )) || fail 'Use only --install or --help.'

project_dir="${KASYNO_PROJECT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)}"
cd -- "$project_dir" || fail 'Cannot open the project directory.'
# A desktop file-portal path can exist while getcwd() fails for Node and Python.
directory_check=(/bin/pwd -P)
if command -v python3 >/dev/null 2>&1; then
  directory_check=(python3 -c 'import os; os.getcwd()')
elif command -v node >/dev/null 2>&1; then
  directory_check=(node -e 'process.cwd()')
fi
if [[ "$project_dir" == /run/user/*/doc/* ]] || ! "${directory_check[@]}" >/dev/null 2>&1; then
  fail "This temporary desktop folder cannot be used by Node/Python. Run: cd \"$HOME/Documents/kasyno-edu\" then: bash scripts/start-dev.sh (or set KASYNO_PROJECT_DIR to the real repository path)."
fi
for file in frontend/package.json frontend/package-lock.json backend/pyproject.toml backend/poetry.lock; do
  [[ -f "$project_dir/$file" ]] || fail "Missing $file. Use a checkout containing both frontend and backend."
done

# Make tools installed for this user available in this terminal.
export PATH="$HOME/.local/bin:$PATH"
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [[ -s "$NVM_DIR/nvm.sh" ]]; then
  set +u
  source "$NVM_DIR/nvm.sh"
  set -u
fi

packages=()
command -v curl >/dev/null 2>&1 || packages+=(curl)
command -v setsid >/dev/null 2>&1 || packages+=(util-linux)
[[ -f /etc/ssl/certs/ca-certificates.crt ]] || packages+=(ca-certificates)
if (( ${#packages[@]} )); then
  command -v apt-get >/dev/null 2>&1 || fail 'Automatic system-package installation requires Ubuntu/Debian.'
  admin=()
  if (( EUID != 0 )); then
    command -v sudo >/dev/null 2>&1 || fail 'sudo is missing. Ask your administrator to install the required Ubuntu packages.'
    admin=(sudo)
  fi
  info "Installing Ubuntu packages: ${packages[*]} (sudo may ask for your password)."
  "${admin[@]}" apt-get update || fail 'Ubuntu package update failed. Check your network/DNS and the error above.'
  "${admin[@]}" apt-get install -y "${packages[@]}" || fail 'Ubuntu package installation failed.'
fi

setup_dir="$(mktemp -d)"
trap 'rm -rf -- "$setup_dir"' EXIT
download() {
  curl --fail --silent --show-error --location --connect-timeout 15 --max-time 120 "$1" -o "$2" ||
    fail 'Download failed. Check your internet connection/DNS and try again.'
}

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  info 'Installing Node.js 24.15.0 and npm 12.0.1 using nvm...'
  if [[ ! -s "$NVM_DIR/nvm.sh" ]]; then
    download https://raw.githubusercontent.com/nvm-sh/nvm/v0.41.0/install.sh "$setup_dir/nvm.sh"
    PROFILE=/dev/null bash "$setup_dir/nvm.sh"
  fi
  set +u
  source "$NVM_DIR/nvm.sh"
  nvm install 24.15.0
  set -u
  npm install --global npm@12.0.1
fi

backend_python=''
for candidate in "$project_dir/backend/.venv/bin/python" python3.13 python3; do
  if command -v "$candidate" >/dev/null 2>&1 &&
    "$candidate" -c 'import sys; sys.exit(not ((3, 13) <= sys.version_info < (4, 0)))' 2>/dev/null; then
    backend_python="$(command -v "$candidate")"
    break
  fi
done

# uv is only a tool installer here; Poetry still manages the backend project.
if [[ -z "$backend_python" ]] || ! command -v poetry >/dev/null 2>&1; then
  if ! command -v uv >/dev/null 2>&1; then
    info 'Installing uv to set up missing Python/Poetry tools...'
    download https://astral.sh/uv/install.sh "$setup_dir/uv.sh"
    UV_INSTALL_DIR="$HOME/.local/bin" UV_NO_MODIFY_PATH=1 sh "$setup_dir/uv.sh"
  fi
  if [[ -z "$backend_python" ]]; then
    info 'Installing Python 3.13 for this user...'
    uv python install 3.13
    backend_python="$(uv python find 3.13)"
  fi
  if ! command -v poetry >/dev/null 2>&1; then
    info 'Installing Poetry 2.5.0 for this user...'
    uv tool install --python "$backend_python" 'poetry==2.5.0'
    export PATH="$(uv tool dir --bin):$PATH"
  fi
fi
rm -rf -- "$setup_dir"
trap - EXIT

node_version="$(node --version)"
npm_version="$(npm --version)"
poetry_version="$(poetry --version)"
info "Node $node_version, npm $npm_version, $poetry_version"
info "Python: $backend_python"
if [[ "$node_version" != v24.15.0 || "$npm_version" != 12.0.1 ]]; then
  printf '[WARN] CI uses Node 24.15.0 and npm 12.0.1. Other versions may behave differently.\n'
fi
export NG_CLI_ANALYTICS=false
export POETRY_NO_INTERACTION=1
export POETRY_VIRTUALENVS_IN_PROJECT=true

cd "$project_dir/frontend"
if "$install" || ! npm ls --depth=0 >/dev/null 2>&1; then
  info 'Installing frontend dependencies (internet access required)...'
  npm ci || fail 'Frontend installation failed. Check the npm error above.'
else
  info 'Frontend dependencies are already installed; skipping installation.'
fi

cd "$project_dir/backend"
backend_check='import sys; assert (3, 13) <= sys.version_info < (4, 0), "Python 3.13 or newer (below 4.0) required"; import uvicorn, fastapi, firebase_admin, pydantic_settings'
if "$install" || ! poetry run python -c "$backend_check" >/dev/null 2>&1; then
  info 'Installing backend dependencies (internet access required)...'
  poetry env use "$backend_python"
  poetry check --lock || fail 'Backend dependency configuration is invalid. Check the Poetry error above.'
  poetry install --with dev --no-root --no-ansi || fail 'Backend installation failed. Check the Poetry error above; Python 3.13 must be installed and available to Poetry.'
  poetry run python -c "$backend_check" || fail 'Backend dependencies are still unavailable. Check the Python error above.'
else
  info 'Backend dependencies are already installed; skipping installation.'
fi
if [[ ! -f .env ]]; then
  [[ -f .env.example ]] || fail 'Missing backend/.env.example.'
  cp -- .env.example .env
  info 'Created backend/.env from .env.example. Existing configuration is never overwritten.'
fi
poetry run python -c 'from src.configs.settings import get_settings; s = get_settings(); print("[INFO] Firebase credentials file found." if s.firebase_credentials_file.is_file() else "[WARN] Firebase credentials are missing. The API can start, but Firebase features will not work. Check backend/.env and your credentials file.")'
poetry run python -c 'import socket
for port in (4200, 8000):
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            raise SystemExit(f"[ERROR] Port {port} is unavailable. Stop the process using it and try again.")'

server_pids=()
cleanup() {
  trap - EXIT INT TERM
  info 'Stopping development servers...'
  for pid in "${server_pids[@]}"; do
    kill -TERM -- "-$pid" 2>/dev/null || true
  done
  wait || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

info 'Starting frontend: http://localhost:4200'
info 'Starting backend: http://localhost:8000 (API docs: http://localhost:8000/docs)'
info 'Wait for both servers to report ready below. Press Ctrl+C to stop both.'
# Separate process groups allow cleanup of npm, Angular and Uvicorn children.
setsid poetry run uvicorn src.main:app --reload --host 127.0.0.1 --port 8000 &
server_pids+=("$!")
cd "$project_dir/frontend"
setsid npm start -- --host 127.0.0.1 --port 4200 &
server_pids+=("$!")

ready=false
for attempt in {1..60}; do
  for pid in "${server_pids[@]}"; do
    kill -0 "$pid" 2>/dev/null || fail 'A development server exited during startup. Check its logs above.'
  done
  if curl --fail --silent --output /dev/null --max-time 2 http://127.0.0.1:8000/api/health &&
    curl --fail --silent --output /dev/null --max-time 2 http://127.0.0.1:4200/; then
    ready=true
    break
  fi
  sleep 1
done
"$ready" || fail 'Servers did not become ready. Check the Angular and Uvicorn logs above.'

printf '\nBoth development servers are ready:\n  Frontend:     http://127.0.0.1:4200\n  Backend docs: http://127.0.0.1:8000/docs\n  Backend API:  http://127.0.0.1:8000/api\n  Health check: http://127.0.0.1:8000/api/health\nPress Ctrl+C to stop both servers.\n\n'

status=0
wait -n "${server_pids[@]}" || status=$?
printf '[ERROR] A development server stopped (exit %s). Check its output above.\n' "$status" >&2
exit 1
