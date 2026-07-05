#!/usr/bin/env bash
#
# Manage the Quantix server: start / stop / restart / status.
#
# Modes:
#   --dev      (default) auto-reload backend + Vite frontend
#   --release            no reload, multiple workers, builds the frontend
#                        and serves it via FastAPI static files
#
# Options:
#   --host <ip>          backend bind address (default 0.0.0.0)
#   --port <port>        backend bind port    (default 9000)
#   --workers <n>        release worker count (default 2; ignored in dev)
#   --frontend-port <p>  Vite dev server port (default 5174; dev only)
#   --no-frontend        do not start/stop the frontend in dev mode
#
# Examples:
#   scripts/server.sh start
#   scripts/server.sh start --release --host 0.0.0.0 --port 9000 --workers 4
#   scripts/server.sh start --dev --no-frontend
#   scripts/server.sh restart --dev --port 9001 --frontend-port 5174
#   scripts/server.sh stop --port 9001
#   scripts/server.sh status

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

APP="backend.main:app"
RUN_DIR="$ROOT_DIR/data"
FRONTEND_DIR="$ROOT_DIR/frontend"

MODE="dev"
HOST="0.0.0.0"
PORT="9000"
WORKERS=""
FRONTEND_PORT="5174"
WITH_FRONTEND=1

usage() {
  sed -n '3,23p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

# --- Argument parsing ----------------------------------------------------

COMMAND="${1:-}"
shift || true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dev) MODE="dev" ;;
    --release|--prod) MODE="release" ;;
    --host) HOST="${2:?--host needs a value}"; shift ;;
    --host=*) HOST="${1#*=}" ;;
    --port) PORT="${2:?--port needs a value}"; shift ;;
    --port=*) PORT="${1#*=}" ;;
    --workers) WORKERS="${2:?--workers needs a value}"; shift ;;
    --workers=*) WORKERS="${1#*=}" ;;
    --frontend-port) FRONTEND_PORT="${2:?--frontend-port needs a value}"; shift ;;
    --frontend-port=*) FRONTEND_PORT="${1#*=}" ;;
    --no-frontend) WITH_FRONTEND=0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

PID_FILE="$RUN_DIR/server-$PORT.pid"
LOG_FILE="$RUN_DIR/server-$PORT.log"
FRONTEND_PID_FILE="$RUN_DIR/frontend-$FRONTEND_PORT.pid"
FRONTEND_LOG_FILE="$RUN_DIR/frontend-$FRONTEND_PORT.log"

# --- Helpers -------------------------------------------------------------

# Resolve how to launch uvicorn: prefer the project venv, then uv, then PATH.
resolve_runner() {
  if [[ -x "$ROOT_DIR/.venv/bin/uvicorn" ]]; then
    RUNNER=("$ROOT_DIR/.venv/bin/uvicorn")
  elif command -v uv >/dev/null 2>&1; then
    RUNNER=(uv run uvicorn)
  elif command -v uvicorn >/dev/null 2>&1; then
    RUNNER=(uvicorn)
  else
    echo "Error: could not find uvicorn (.venv, uv, or PATH)." >&2
    exit 1
  fi
}

# Resolve how to run the frontend build: prefer pnpm, then npm.
resolve_build_runner() {
  if command -v pnpm >/dev/null 2>&1; then
    BUILD_RUNNER=(pnpm --dir "$FRONTEND_DIR" run build)
  elif command -v npm >/dev/null 2>&1; then
    BUILD_RUNNER=(npm --prefix "$FRONTEND_DIR" run build)
  else
    echo "Error: could not find pnpm or npm for frontend build." >&2
    exit 1
  fi
}

# Resolve how to launch Vite: prefer the local install, then npx.
resolve_frontend_runner() {
  if [[ -x "$FRONTEND_DIR/node_modules/.bin/vite" ]]; then
    FRUNNER=("$FRONTEND_DIR/node_modules/.bin/vite")
  elif command -v npx >/dev/null 2>&1; then
    FRUNNER=(npx vite)
  else
    echo "Error: could not find vite (frontend/node_modules or npx)." >&2
    exit 1
  fi
}

# Echo the running PID from a pid file if that process is alive, else nothing
# (and clean up a stale pid file). Defaults to the backend pid file.
running_pid() {
  local pid_file="${1:-$PID_FILE}"
  [[ -f "$pid_file" ]] || return 0
  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "$pid"
  else
    rm -f "$pid_file"
  fi
}

# Terminate the process recorded in a pid file (TERM, then KILL on timeout).
stop_pid_file() {
  local pid_file="$1" label="$2" pid
  pid="$(running_pid "$pid_file")"
  if [[ -z "$pid" ]]; then
    echo "$label not running."
    return 0
  fi
  echo "Stopping $label (pid $pid) ..."
  kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 20); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.5
  done
  if kill -0 "$pid" 2>/dev/null; then
    echo "Force killing $label (pid $pid) ..."
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$pid_file"
  echo "$label stopped."
}

do_start() {
  local pid
  pid="$(running_pid)"
  if [[ -n "$pid" ]]; then
    echo "Already running on port $PORT (pid $pid)."
    return 0
  fi

  # Kill any orphaned process holding the port (e.g. started outside this script).
  local port_pid
  port_pid="$(lsof -t -i :"$PORT" 2>/dev/null || true)"
  if [[ -n "$port_pid" ]]; then
    echo "Port $PORT is held by orphaned process (pid $port_pid), killing ..."
    kill $port_pid 2>/dev/null || true
    sleep 1
  fi

  mkdir -p "$RUN_DIR"
  resolve_runner

  # In release mode, build the frontend so FastAPI can serve it statically.
  if [[ "$MODE" == "release" ]]; then
    resolve_build_runner
    echo "Building frontend ..."
    if ! "${BUILD_RUNNER[@]}"; then
      echo "Error: frontend build failed." >&2
      exit 1
    fi
    echo "Frontend built successfully."
  fi

  local cmd=("${RUNNER[@]}" "$APP" --host "$HOST" --port "$PORT")
  if [[ "$MODE" == "dev" ]]; then
    cmd+=(--reload)
  else
    cmd+=(--workers "${WORKERS:-2}")
  fi

  echo "Starting ($MODE) on $HOST:$PORT ..."
  nohup "${cmd[@]}" >>"$LOG_FILE" 2>&1 &
  pid=$!
  echo "$pid" >"$PID_FILE"

  # Give it a moment to bind, then confirm it survived startup.
  sleep 1
  if kill -0 "$pid" 2>/dev/null; then
    echo "Backend started (pid $pid). Logs: $LOG_FILE"
  else
    echo "Backend failed to start; see $LOG_FILE" >&2
    rm -f "$PID_FILE"
    exit 1
  fi
}

do_start_frontend() {
  local pid
  pid="$(running_pid "$FRONTEND_PID_FILE")"
  if [[ -n "$pid" ]]; then
    echo "Frontend already running on port $FRONTEND_PORT (pid $pid)."
    return 0
  fi

  mkdir -p "$RUN_DIR"
  resolve_frontend_runner

  echo "Starting frontend (Vite) on port $FRONTEND_PORT ..."
  pushd "$FRONTEND_DIR" >/dev/null
  # Tell Vite which port the backend listens on so /api proxy stays in sync.
  VITE_BACKEND_PORT="$PORT" nohup "${FRUNNER[@]}" \
    --host "$HOST" --port "$FRONTEND_PORT" --strictPort >>"$FRONTEND_LOG_FILE" 2>&1 &
  pid=$!
  popd >/dev/null
  echo "$pid" >"$FRONTEND_PID_FILE"

  sleep 1
  if kill -0 "$pid" 2>/dev/null; then
    echo "Frontend started (pid $pid). Logs: $FRONTEND_LOG_FILE"
  else
    echo "Frontend failed to start; see $FRONTEND_LOG_FILE" >&2
    rm -f "$FRONTEND_PID_FILE"
    exit 1
  fi
}

do_stop() {
  stop_pid_file "$PID_FILE" "Backend (port $PORT)"
}

do_stop_frontend() {
  stop_pid_file "$FRONTEND_PID_FILE" "Frontend (port $FRONTEND_PORT)"
}

do_status() {
  local pid
  pid="$(running_pid)"
  if [[ -n "$pid" ]]; then
    echo "Backend running on port $PORT (pid $pid). Logs: $LOG_FILE"
  else
    echo "Backend not running on port $PORT."
  fi
}

do_status_frontend() {
  local pid
  pid="$(running_pid "$FRONTEND_PID_FILE")"
  if [[ -n "$pid" ]]; then
    echo "Frontend running on port $FRONTEND_PORT (pid $pid). Logs: $FRONTEND_LOG_FILE"
  else
    echo "Frontend not running on port $FRONTEND_PORT."
  fi
}

# --- Dispatch ------------------------------------------------------------

# Frontend is a dev-only concern (Vite dev server); in release mode the
# frontend is built and served statically by FastAPI.
frontend_active() {
  [[ "$MODE" == "dev" && "$WITH_FRONTEND" == "1" ]]
}
# Also touch the frontend on stop/status if a pid file is lying around.
frontend_present() {
  frontend_active || [[ -f "$FRONTEND_PID_FILE" ]]
}

case "$COMMAND" in
  start)
    do_start
    frontend_active && do_start_frontend
    ;;
  stop)
    do_stop
    frontend_present && do_stop_frontend
    ;;
  restart)
    do_stop
    frontend_present && do_stop_frontend
    do_start
    frontend_active && do_start_frontend
    ;;
  status)
    do_status
    frontend_present && do_status_frontend
    ;;
  ""|-h|--help) usage ;;
  *) echo "Unknown command: $COMMAND" >&2; usage; exit 1 ;;
esac
