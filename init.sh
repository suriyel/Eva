#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Harness — environment bootstrap (Unix / macOS)
#
# Idempotent, fail-fast, version-pinned per env-guide.md §3 "Tool version lock"
#   Python  >= 3.11   (CON-001 / Design §3.4)
#   Node    >= 20     (Vite 5 / shadcn)
#   npm     >= 10
#   pytest>=8.3, pytest-asyncio>=0.24, pytest-cov>=5.0,
#   ruff>=0.6, black>=24.8, mypy>=1.11
#   vite>=5.4, vitest>=2.1, playwright>=1.48
#   pyinstaller>=6.10 (M4 / F17 only — installed into dev deps so the spec file
#   can be exercised locally; runtime packaging step is opt-in).
#
# Services (api / ui-dev) are NOT started by this script — see env-guide.md §1.
# This script only produces stub launchers at scripts/svc-*-start.{sh,ps1}
# if they do not already exist.
# ---------------------------------------------------------------------------
set -euo pipefail

cd "$(dirname "$0")"
REPO_ROOT="$(pwd)"

echo "=== Harness Environment Bootstrap (Unix) ==="
echo "Repo root: ${REPO_ROOT}"

# ---------------------------------------------------------------------------
# Step 1 — runtime: Python 3.11+
# ---------------------------------------------------------------------------
PYTHON_BIN=""
for candidate in python3.12 python3.11 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON_BIN="$candidate"
        break
    fi
done
if [ -z "${PYTHON_BIN}" ]; then
    echo "ERROR: Python 3.11+ not found. Install via your system package manager,"
    echo "       pyenv, or https://www.python.org/downloads/." >&2
    exit 1
fi

PY_VER="$("${PYTHON_BIN}" -c 'import sys; print("%d.%d" % (sys.version_info[0], sys.version_info[1]))')"
PY_MAJOR="${PY_VER%%.*}"
PY_MINOR="${PY_VER##*.}"
if [ "${PY_MAJOR}" -lt 3 ] || { [ "${PY_MAJOR}" -eq 3 ] && [ "${PY_MINOR}" -lt 11 ]; }; then
    echo "ERROR: detected Python ${PY_VER} at $(command -v "${PYTHON_BIN}"); need >= 3.11." >&2
    exit 1
fi
echo "Python ${PY_VER} OK ($(command -v "${PYTHON_BIN}"))"

# ---------------------------------------------------------------------------
# Step 2 — Python virtual environment (.venv/)
# ---------------------------------------------------------------------------
VENV_DIR=".venv"
if [ ! -d "${VENV_DIR}" ]; then
    echo "Creating virtualenv at ${VENV_DIR}/ ..."
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
else
    echo "Reusing existing virtualenv at ${VENV_DIR}/"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

# ---------------------------------------------------------------------------
# Step 3 — Python dependencies (quiet)
# ---------------------------------------------------------------------------
python -m pip install --upgrade --disable-pip-version-check pip setuptools wheel >/dev/null

# Runtime deps (if requirements.txt already populated by later features)
if [ -f "requirements.txt" ]; then
    echo "Installing runtime deps from requirements.txt ..."
    pip install --disable-pip-version-check -r requirements.txt
else
    echo "No requirements.txt yet — skipping runtime deps."
fi

if [ -f "requirements-dev.txt" ]; then
    echo "Installing dev deps from requirements-dev.txt ..."
    pip install --disable-pip-version-check -r requirements-dev.txt
else
    echo "Installing pinned dev toolchain (no requirements-dev.txt yet) ..."
    pip install --disable-pip-version-check \
        "pytest>=8.3,<9" \
        "pytest-asyncio>=0.24,<1" \
        "pytest-cov>=5.0,<6" \
        "ruff>=0.6,<1" \
        "black>=24.8,<25" \
        "mypy>=1.11,<2" \
        "pyinstaller>=6.10,<7"
fi

# ---------------------------------------------------------------------------
# Step 4 — Node.js toolchain for apps/ui/ (Node >= 20)
# ---------------------------------------------------------------------------
UI_DIR="apps/ui"
if command -v node >/dev/null 2>&1; then
    NODE_VER="$(node --version | sed 's/^v//')"
    NODE_MAJOR="${NODE_VER%%.*}"
    if [ "${NODE_MAJOR}" -lt 20 ]; then
        echo "WARN: Node ${NODE_VER} found but Harness requires Node >= 20." >&2
        echo "      Install via nvm / fnm / system package manager and re-run." >&2
    else
        echo "Node ${NODE_VER} OK"
    fi
else
    echo "WARN: node not found on PATH. Install Node >= 20 (nvm / fnm / system pkg)." >&2
    echo "      Frontend install will be skipped; re-run init.sh after installing Node." >&2
fi

if [ -d "${UI_DIR}" ] && command -v node >/dev/null 2>&1; then
    if [ -f "${UI_DIR}/package-lock.json" ]; then
        echo "Installing UI deps via 'npm ci' in ${UI_DIR} ..."
        ( cd "${UI_DIR}" && npm ci )
    elif [ -f "${UI_DIR}/package.json" ]; then
        echo "Installing UI deps via 'npm install' in ${UI_DIR} ..."
        ( cd "${UI_DIR}" && npm install )
    else
        echo "No ${UI_DIR}/package.json yet — skipping UI deps."
    fi
else
    echo "Skipping UI deps (directory ${UI_DIR}/ missing or node unavailable)."
fi

# ---------------------------------------------------------------------------
# Step 5 — service start stubs (env-guide.md §1 references these)
# ---------------------------------------------------------------------------
mkdir -p scripts

write_if_missing() {
    local path="$1"
    local body="$2"
    local mode="$3"
    if [ ! -f "${path}" ]; then
        printf '%s' "${body}" > "${path}"
        chmod "${mode}" "${path}"
        echo "Wrote stub ${path}"
    fi
}

API_SH=$'#!/usr/bin/env bash\n# Harness api service launcher (FastAPI + uvicorn, 127.0.0.1:8765)\n# See env-guide.md \xc2\xa71. Replaced with real launcher once F01/F02 land.\nset -euo pipefail\ncd "$(dirname "$0")/.."\nif [ -f ".venv/bin/activate" ]; then\n    # shellcheck disable=SC1091\n    source ".venv/bin/activate"\nfi\nexport HARNESS_HOME="${HARNESS_HOME:-$HOME/.harness}"\nif python -c "import harness.api" >/dev/null 2>&1; then\n    exec uvicorn harness.api:app --host 127.0.0.1 --port 8765\nfi\necho "[svc-api-start] harness.api not implemented yet — placeholder running." >&2\nwhile true; do sleep 3600; done\n'

UI_SH=$'#!/usr/bin/env bash\n# Harness ui-dev service launcher (Vite dev server, 127.0.0.1:5173)\n# See env-guide.md \xc2\xa71. Replaced with real launcher once apps/ui/ lands.\nset -euo pipefail\ncd "$(dirname "$0")/.."\nif [ -d "apps/ui" ] && [ -f "apps/ui/package.json" ]; then\n    cd apps/ui\n    exec npm run dev -- --host 127.0.0.1 --port 5173\nfi\necho "[svc-ui-dev-start] apps/ui/ not scaffolded yet — placeholder running." >&2\nwhile true; do sleep 3600; done\n'

API_PS=$'# Harness api service launcher (Windows). See env-guide.md \xc2\xa71.\n$ErrorActionPreference = "Stop"\nSet-Location (Join-Path $PSScriptRoot "..")\nif (Test-Path ".venv\\Scripts\\Activate.ps1") {\n    & ".venv\\Scripts\\Activate.ps1"\n}\nif (-not $env:HARNESS_HOME) { $env:HARNESS_HOME = Join-Path $HOME ".harness" }\n$hasApi = $false\ntry { & python -c "import harness.api" 2>$null; if ($LASTEXITCODE -eq 0) { $hasApi = $true } } catch {}\nif ($hasApi) {\n    & uvicorn harness.api:app --host 127.0.0.1 --port 8765\n} else {\n    Write-Warning "[svc-api-start] harness.api not implemented yet \xe2\x80\x94 placeholder running."\n    while ($true) { Start-Sleep -Seconds 3600 }\n}\n'

UI_PS=$'# Harness ui-dev service launcher (Windows). See env-guide.md \xc2\xa71.\n$ErrorActionPreference = "Stop"\nSet-Location (Join-Path $PSScriptRoot "..")\nif ((Test-Path "apps\\ui") -and (Test-Path "apps\\ui\\package.json")) {\n    Set-Location "apps\\ui"\n    & npm run dev -- --host 127.0.0.1 --port 5173\n} else {\n    Write-Warning "[svc-ui-dev-start] apps/ui/ not scaffolded yet \xe2\x80\x94 placeholder running."\n    while ($true) { Start-Sleep -Seconds 3600 }\n}\n'

write_if_missing "scripts/svc-api-start.sh"    "${API_SH}" 0755
write_if_missing "scripts/svc-ui-dev-start.sh" "${UI_SH}"  0755
write_if_missing "scripts/svc-api-start.ps1"    "${API_PS}" 0644
write_if_missing "scripts/svc-ui-dev-start.ps1" "${UI_PS}"  0644

# ---------------------------------------------------------------------------
# Step 6 — verify
# ---------------------------------------------------------------------------
echo ""
echo "=== Environment Check ==="
echo "python : $(python --version 2>&1)"
echo "pip    : $(pip --version 2>&1 | awk '{print $1, $2}')"
if command -v node >/dev/null 2>&1; then
    echo "node   : $(node --version 2>&1)"
    echo "npm    : $(npm --version 2>&1)"
else
    echo "node   : (not installed — required for apps/ui/)"
fi
for tool in pytest ruff black mypy; do
    if command -v "${tool}" >/dev/null 2>&1; then
        echo "$(printf '%-7s' "${tool}"): $("${tool}" --version 2>&1 | head -1)"
    fi
done
echo ""
echo "Activate with: source ${VENV_DIR}/bin/activate"
echo "Environment ready."
