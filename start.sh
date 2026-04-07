#!/bin/bash

export PYTHONUNBUFFERED=1

cleanup() {
  echo "Shutting down..."
  kill $(jobs -p) 2>/dev/null
  exit 0
}
trap cleanup EXIT INT TERM

source .venv/bin/activate

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

echo "Starting Temporal dev server..."
temporal server start-dev &> temporal_logs.log &
wait_for_log temporal_logs.log "Temporal CLI 1.6.2 (Server 1.30.2, UI 2.45.3)" && echo "Temporal started"

echo "Starting worker..."
python -m workflow.worker &> worker_logs.log &
wait_for_log worker_logs.log "Worker started" && echo "Worker started"

echo "Starting gRPC server..."
python -m server.grpc_server &> grpc_server_logs.log &
wait_for_log grpc_server_logs.log "gRPC server listening on" && echo "gRPC server started"

echo "All services up."
while true; do
  for pid in $(jobs -p); do
    if ! kill -0 $pid 2>/dev/null; then
      echo "A service exited, shutting down..."
      exit 1
    fi
  done
  sleep 1
done