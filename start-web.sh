#!/usr/bin/env bash
set -euo pipefail

API_LOG="logs/fastapi.txt"
WEB_LOG="logs/svelte.txt"

cleanup() {
  echo
  echo "Stopping services..."

  if [[ -n "${API_PID:-}" ]]; then
    kill "$API_PID" 2>/dev/null || true
  fi

  if [[ -n "${WEB_PID:-}" ]]; then
    kill "$WEB_PID" 2>/dev/null || true
  fi

  wait "${API_PID:-}" 2>/dev/null || true
  wait "${WEB_PID:-}" 2>/dev/null || true

  echo "Stopped."
}

trap cleanup INT TERM EXIT

mkdir -p logs

echo "Starting FastAPI..."
uvicorn app.main:app --reload --port 8000 >"$API_LOG" 2>&1 &
API_PID=$!

echo "Starting SvelteKit..."
(
  cd web
  npm run dev
) >"$WEB_LOG" 2>&1 &
WEB_PID=$!

echo "FastAPI PID: $API_PID"
echo "Svelte PID:  $WEB_PID"
echo
echo "Logs:"
echo "  FastAPI: $API_LOG"
echo "  Svelte : $WEB_LOG"
echo
echo "Press Ctrl-C to stop both."

wait "$API_PID" "$WEB_PID"