#!/usr/bin/env bash
# Harness ui-dev service launcher (Vite dev server, 127.0.0.1:5173)
# See env-guide.md §1. Replaced with real launcher once apps/ui/ lands.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -d "apps/ui" ] && [ -f "apps/ui/package.json" ]; then
    cd apps/ui
    exec npm run dev -- --host 127.0.0.1 --port 5173
fi
echo "[svc-ui-dev-start] apps/ui/ not scaffolded yet — placeholder running." >&2
while true; do sleep 3600; done
