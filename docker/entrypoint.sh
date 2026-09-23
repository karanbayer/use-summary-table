#!/bin/sh
set -eu

# Start the AI relay API (loopback only; nginx proxies /api/*).
node /app/server/index.mjs &
API_PID=$!

cleanup() {
  kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Wait until the API accepts connections (or fail fast).
i=0
while [ "$i" -lt 30 ]; do
  if wget -qO- http://127.0.0.1:3000/health >/dev/null 2>&1; then
    break
  fi
  i=$((i + 1))
  sleep 0.2
done

if ! wget -qO- http://127.0.0.1:3000/health >/dev/null 2>&1; then
  echo "API failed to become healthy on :3000" >&2
  exit 1
fi

exec nginx -g "daemon off;"
