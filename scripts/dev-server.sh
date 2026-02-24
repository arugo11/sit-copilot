#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${ROOT_DIR}/.runtime"
mkdir -p "${RUNTIME_DIR}"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
WEAVE_ENABLED_DEFAULT="${WEAVE_ENABLED:-false}"

BACKEND_PID_FILE="${RUNTIME_DIR}/backend.pid"
FRONTEND_PID_FILE="${RUNTIME_DIR}/frontend.pid"
BACKEND_LOG="${RUNTIME_DIR}/backend.log"
FRONTEND_LOG="${RUNTIME_DIR}/frontend.log"

print_usage() {
  cat <<'USAGE'
Usage:
  scripts/dev-server.sh <action> [target]

Actions:
  start     Start service(s)
  stop      Stop service(s)
  restart   Restart service(s)
  status    Show service status
  logs      Tail logs (default: backend)

Targets:
  backend | frontend | all

Examples:
  scripts/dev-server.sh start all
  scripts/dev-server.sh restart backend
  scripts/dev-server.sh status all
  scripts/dev-server.sh logs frontend
USAGE
}

is_pid_running() {
  local pid="$1"
  [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null
}

read_pid_file() {
  local pid_file="$1"
  if [[ -f "${pid_file}" ]]; then
    tr -d '[:space:]' <"${pid_file}"
  fi
}

sync_pid_file() {
  local pid_file="$1"
  local pid="$2"
  printf '%s\n' "${pid}" >"${pid_file}"
}

remove_stale_pid_file() {
  local pid_file="$1"
  if [[ -f "${pid_file}" ]]; then
    rm -f "${pid_file}"
  fi
}

wait_for_exit() {
  local pid="$1"
  local max_loops="${2:-50}"
  for _ in $(seq 1 "${max_loops}"); do
    if ! is_pid_running "${pid}"; then
      return 0
    fi
    sleep 0.1
  done
  return 1
}

wait_for_listen() {
  local port="$1"
  local max_loops="${2:-80}"
  for _ in $(seq 1 "${max_loops}"); do
    if lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.1
  done
  return 1
}

port_listener_pid() {
  local port="$1"
  lsof -t -nP -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null | head -n 1 || true
}

detect_service_pid() {
  local pid_file="$1"
  local listen_port="$2"
  local cmd_fragment="$3"

  local pid
  pid="$(read_pid_file "${pid_file}")"
  if is_pid_running "${pid:-}"; then
    local cmd_from_pid_file
    cmd_from_pid_file="$(ps -p "${pid}" -o cmd= 2>/dev/null || true)"
    if [[ "${cmd_from_pid_file}" == *"${cmd_fragment}"* ]] && \
      lsof -nP -a -p "${pid}" -iTCP:"${listen_port}" -sTCP:LISTEN >/dev/null 2>&1; then
      printf '%s\n' "${pid}"
      return 0
    fi
  fi

  pid="$(port_listener_pid "${listen_port}")"
  if is_pid_running "${pid:-}"; then
    local cmd
    cmd="$(ps -p "${pid}" -o cmd= 2>/dev/null || true)"
    if [[ "${cmd}" == *"${cmd_fragment}"* ]]; then
      sync_pid_file "${pid_file}" "${pid}"
      printf '%s\n' "${pid}"
      return 0
    fi
  fi

  remove_stale_pid_file "${pid_file}"
  return 1
}

start_backend() {
  local pid
  if pid="$(detect_service_pid "${BACKEND_PID_FILE}" "${BACKEND_PORT}" "uvicorn")"; then
    echo "backend is already running (pid=${pid})."
    return 0
  fi

  local occupying_pid
  occupying_pid="$(port_listener_pid "${BACKEND_PORT}")"
  if [[ -n "${occupying_pid}" ]]; then
    echo "backend start failed: port ${BACKEND_PORT} is in use by pid ${occupying_pid}." >&2
    return 1
  fi

  (
    cd "${ROOT_DIR}"
    WEAVE_ENABLED="${WEAVE_ENABLED_DEFAULT}" \
      nohup uv run uvicorn app.main:app --host "${BACKEND_HOST}" --port "${BACKEND_PORT}" \
      >"${BACKEND_LOG}" 2>&1 &
    sync_pid_file "${BACKEND_PID_FILE}" "$!"
  )

  pid="$(read_pid_file "${BACKEND_PID_FILE}")"
  if ! is_pid_running "${pid:-}"; then
    echo "backend start failed. check log: ${BACKEND_LOG}" >&2
    return 1
  fi
  if ! wait_for_listen "${BACKEND_PORT}" 120; then
    echo "backend start timeout. check log: ${BACKEND_LOG}" >&2
    return 1
  fi

  echo "backend started (pid=${pid}) on http://${BACKEND_HOST}:${BACKEND_PORT}"
}

stop_backend() {
  local pid
  if ! pid="$(detect_service_pid "${BACKEND_PID_FILE}" "${BACKEND_PORT}" "uvicorn")"; then
    echo "backend is already stopped."
    return 0
  fi

  kill "${pid}" 2>/dev/null || true
  if ! wait_for_exit "${pid}" 80; then
    kill -9 "${pid}" 2>/dev/null || true
  fi
  remove_stale_pid_file "${BACKEND_PID_FILE}"
  echo "backend stopped."
}

start_frontend() {
  local pid
  if pid="$(detect_service_pid "${FRONTEND_PID_FILE}" "${FRONTEND_PORT}" "vite")"; then
    echo "frontend is already running (pid=${pid})."
    return 0
  fi

  local occupying_pid
  occupying_pid="$(port_listener_pid "${FRONTEND_PORT}")"
  if [[ -n "${occupying_pid}" ]]; then
    echo "frontend start failed: port ${FRONTEND_PORT} is in use by pid ${occupying_pid}." >&2
    return 1
  fi

  (
    cd "${ROOT_DIR}"
    nohup npm run dev --prefix frontend -- --host "${FRONTEND_HOST}" --port "${FRONTEND_PORT}" \
      >"${FRONTEND_LOG}" 2>&1 &
    sync_pid_file "${FRONTEND_PID_FILE}" "$!"
  )

  pid="$(read_pid_file "${FRONTEND_PID_FILE}")"
  if ! is_pid_running "${pid:-}"; then
    echo "frontend start failed. check log: ${FRONTEND_LOG}" >&2
    return 1
  fi
  if ! wait_for_listen "${FRONTEND_PORT}" 120; then
    echo "frontend start timeout. check log: ${FRONTEND_LOG}" >&2
    return 1
  fi

  echo "frontend started (pid=${pid}) on http://${FRONTEND_HOST}:${FRONTEND_PORT}"
}

stop_frontend() {
  local pid
  if ! pid="$(detect_service_pid "${FRONTEND_PID_FILE}" "${FRONTEND_PORT}" "vite")"; then
    echo "frontend is already stopped."
    return 0
  fi

  kill "${pid}" 2>/dev/null || true
  if ! wait_for_exit "${pid}" 80; then
    kill -9 "${pid}" 2>/dev/null || true
  fi
  remove_stale_pid_file "${FRONTEND_PID_FILE}"
  echo "frontend stopped."
}

status_backend() {
  local pid
  if pid="$(detect_service_pid "${BACKEND_PID_FILE}" "${BACKEND_PORT}" "uvicorn")"; then
    echo "backend: running (pid=${pid}) url=http://${BACKEND_HOST}:${BACKEND_PORT} log=${BACKEND_LOG}"
  else
    echo "backend: stopped"
  fi
}

status_frontend() {
  local pid
  if pid="$(detect_service_pid "${FRONTEND_PID_FILE}" "${FRONTEND_PORT}" "vite")"; then
    echo "frontend: running (pid=${pid}) url=http://${FRONTEND_HOST}:${FRONTEND_PORT} log=${FRONTEND_LOG}"
  else
    echo "frontend: stopped"
  fi
}

logs_backend() {
  touch "${BACKEND_LOG}"
  tail -f "${BACKEND_LOG}"
}

logs_frontend() {
  touch "${FRONTEND_LOG}"
  tail -f "${FRONTEND_LOG}"
}

run_action() {
  local action="$1"
  local target="$2"

  case "${action}" in
    start)
      case "${target}" in
        backend) start_backend ;;
        frontend) start_frontend ;;
        all) start_backend; start_frontend ;;
        *) print_usage; exit 1 ;;
      esac
      ;;
    stop)
      case "${target}" in
        backend) stop_backend ;;
        frontend) stop_frontend ;;
        all) stop_frontend; stop_backend ;;
        *) print_usage; exit 1 ;;
      esac
      ;;
    restart)
      case "${target}" in
        backend) stop_backend; start_backend ;;
        frontend) stop_frontend; start_frontend ;;
        all) stop_frontend; stop_backend; start_backend; start_frontend ;;
        *) print_usage; exit 1 ;;
      esac
      ;;
    status)
      case "${target}" in
        backend) status_backend ;;
        frontend) status_frontend ;;
        all) status_backend; status_frontend ;;
        *) print_usage; exit 1 ;;
      esac
      ;;
    logs)
      case "${target}" in
        backend) logs_backend ;;
        frontend) logs_frontend ;;
        *) print_usage; exit 1 ;;
      esac
      ;;
    *)
      print_usage
      exit 1
      ;;
  esac
}

ACTION="${1:-status}"
TARGET="${2:-all}"
run_action "${ACTION}" "${TARGET}"
