#!/usr/bin/env bash

set -euo pipefail

export PYTHONUNBUFFERED=1
SMOKE_TEST=false
LOG_DIR="logs"

if [ "${1:-}" = "--smoke-test" ]; then
  SMOKE_TEST=true
elif [ "${1:-}" != "" ]; then
  echo "Usage: $0 [--smoke-test]"
  exit 1
fi

cleanup() {
  echo "Shutting down..."
  kill $(jobs -p) 2>/dev/null
  exit 0
}
trap cleanup EXIT INT TERM

if [ -z "${CI:-}" ]; then
  source .venv/bin/activate
fi

wait_for_log() {
  local logfile=$1
  local pattern=$2
  local timeout=${3:-30}
  local i=0
  until grep -q "$pattern" "$logfile" 2>/dev/null; do
    sleep 0.5
    i=$((i + 1))
    if [ $i -ge $((timeout * 2)) ]; then
      echo "Timed out waiting for: $pattern"
      exit 1
    fi
  done
}

mkdir -p "$LOG_DIR"

echo "Starting Temporal dev server..."
temporal server start-dev &> "$LOG_DIR/temporal_logs.log" &
wait_for_log "$LOG_DIR/temporal_logs.log" "Temporal CLI 1.6.2 (Server 1.30.2, UI 2.45.3)" &&
  echo "Temporal started"

echo "Starting worker..."
python -m workflow.worker &> "$LOG_DIR/worker_logs.log" &
wait_for_log "$LOG_DIR/worker_logs.log" "Worker started" && echo "Worker started"

echo "Starting gRPC server..."
python -m server.grpc_server &> "$LOG_DIR/grpc_server_logs.log" &
wait_for_log "$LOG_DIR/grpc_server_logs.log" "gRPC server listening on" &&
  echo "gRPC server started"

echo "All services up."

if [ "$SMOKE_TEST" = true ]; then
  exit 0
fi

while true; do
  for pid in $(jobs -p); do
    if ! kill -0 $pid 2>/dev/null; then
      echo "A service exited, shutting down..."
      exit 1
    fi
  done
  sleep 1
done