#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR/backend"

PYTHON_BIN="python3"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || PYTHON_BIN="python"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  "$PYTHON_BIN" -m venv .venv
fi

# Works in Git Bash on Windows and standard Bash environments.
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate
pip install -q -r requirements.txt

if [ ! -f "$ROOT_DIR/.env" ]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
fi

rm -f controlplane.db controlplane.db-wal controlplane.db-shm

echo "Starting backend on http://localhost:8000 ..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
sleep 2

cd "$ROOT_DIR/frontend"
echo "Starting frontend on http://localhost:3000 ..."
"$PYTHON_BIN" -m http.server 3000 &
FRONTEND_PID=$!

echo ""
echo "ControlPlane.ai is running"
echo "Live Control: http://localhost:3000"
echo "API docs:     http://localhost:8000/docs"
echo "Press Ctrl+C to stop."

trap 'kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true' EXIT INT TERM
wait "$BACKEND_PID"
