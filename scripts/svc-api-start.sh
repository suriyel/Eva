#!/usr/bin/env bash
# Harness api service launcher (FastAPI + uvicorn, 127.0.0.1:8765)
# See env-guide.md §1. Replaced with real launcher once F01/F02 land.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source ".venv/bin/activate"
fi
export HARNESS_HOME="${HARNESS_HOME:-$HOME/.harness}"
if python -c "import harness.api" >/dev/null 2>&1; then
    exec uvicorn harness.api:app --host 127.0.0.1 --port 8765
fi
echo "[svc-api-start] harness.api not implemented yet — placeholder running." >&2
while true; do sleep 3600; done
