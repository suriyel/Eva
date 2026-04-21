# ---------------------------------------------------------------------------
# Harness - environment bootstrap (Windows / PowerShell)
#
# Idempotent, fail-fast, version-pinned per env-guide.md section 3.
#   Python  >= 3.11   (CON-001 / Design section 3.4)
#   Node    >= 20     (Vite 5 / shadcn)
#   npm     >= 10
#   pytest>=8.3, pytest-asyncio>=0.24, pytest-cov>=5.0,
#   ruff>=0.6, black>=24.8, mypy>=1.11
#   vite>=5.4, vitest>=2.1, playwright>=1.48
#   pyinstaller>=6.10 (M4 / F17 only)
#
# Services (api / ui-dev) are NOT started by this script - see env-guide.md section 1.
# This script only produces stub launchers at scripts\svc-*-start.{sh,ps1}
# if they do not already exist.
# ---------------------------------------------------------------------------
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$RepoRoot = (Get-Location).Path

Write-Host "=== Harness Environment Bootstrap (Windows) ==="
Write-Host "Repo root: $RepoRoot"

# ---------------------------------------------------------------------------
# Step 1 - runtime: Python 3.11+
# ---------------------------------------------------------------------------
$PythonBin = $null
foreach ($candidate in @("py", "python3.12", "python3.11", "python3", "python")) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) { $PythonBin = $candidate; break }
}
if (-not $PythonBin) {
    Write-Error "Python 3.11+ not found. Install from https://www.python.org/downloads/ or via winget."
    exit 1
}

if ($PythonBin -eq "py") {
    $pyVer = & py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    $PythonLauncher = @("py", "-3")
} else {
    $pyVer = & $PythonBin -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    $PythonLauncher = @($PythonBin)
}
$pyParts = $pyVer.Split(".")
$pyMajor = [int]$pyParts[0]
$pyMinor = [int]$pyParts[1]
if (($pyMajor -lt 3) -or (($pyMajor -eq 3) -and ($pyMinor -lt 11))) {
    Write-Error "Detected Python $pyVer; need >= 3.11."
    exit 1
}
Write-Host "Python $pyVer OK"

# ---------------------------------------------------------------------------
# Step 2 - Python virtual environment (.venv\)
# ---------------------------------------------------------------------------
$VenvDir = ".venv"
if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating virtualenv at $VenvDir\ ..."
    & $PythonLauncher[0] $PythonLauncher[1..($PythonLauncher.Length - 1)] -m venv $VenvDir
} else {
    Write-Host "Reusing existing virtualenv at $VenvDir\"
}

$activate = Join-Path $VenvDir "Scripts\Activate.ps1"
if (-not (Test-Path $activate)) {
    Write-Error "venv activation script missing at $activate"
    exit 1
}
& $activate

# ---------------------------------------------------------------------------
# Step 3 - Python dependencies
# ---------------------------------------------------------------------------
python -m pip install --upgrade --disable-pip-version-check pip setuptools wheel | Out-Null

if (Test-Path "requirements.txt") {
    Write-Host "Installing runtime deps from requirements.txt ..."
    pip install --disable-pip-version-check -r requirements.txt
} else {
    Write-Host "No requirements.txt yet - skipping runtime deps."
}

if (Test-Path "requirements-dev.txt") {
    Write-Host "Installing dev deps from requirements-dev.txt ..."
    pip install --disable-pip-version-check -r requirements-dev.txt
} else {
    Write-Host "Installing pinned dev toolchain (no requirements-dev.txt yet) ..."
    pip install --disable-pip-version-check `
        "pytest>=8.3,<9" `
        "pytest-asyncio>=0.24,<1" `
        "pytest-cov>=5.0,<6" `
        "ruff>=0.6,<1" `
        "black>=24.8,<25" `
        "mypy>=1.11,<2" `
        "pyinstaller>=6.10,<7"
}

# ---------------------------------------------------------------------------
# Step 4 - Node.js toolchain for apps\ui\ (Node >= 20)
# ---------------------------------------------------------------------------
$UiDir = "apps\ui"
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if ($nodeCmd) {
    $nodeRaw = (& node --version).TrimStart("v")
    $nodeMajor = [int]($nodeRaw.Split(".")[0])
    if ($nodeMajor -lt 20) {
        Write-Warning "Node $nodeRaw found but Harness requires Node >= 20. Install nvm-windows / fnm / system pkg."
    } else {
        Write-Host "Node $nodeRaw OK"
    }
} else {
    Write-Warning "node not found on PATH. Install Node >= 20 (nvm-windows / fnm). UI deps will be skipped."
}

if ((Test-Path $UiDir) -and $nodeCmd) {
    if (Test-Path (Join-Path $UiDir "package-lock.json")) {
        Write-Host "Installing UI deps via 'npm ci' in $UiDir ..."
        Push-Location $UiDir
        try { npm ci } finally { Pop-Location }
    } elseif (Test-Path (Join-Path $UiDir "package.json")) {
        Write-Host "Installing UI deps via 'npm install' in $UiDir ..."
        Push-Location $UiDir
        try { npm install } finally { Pop-Location }
    } else {
        Write-Host "No $UiDir\package.json yet - skipping UI deps."
    }
} else {
    Write-Host "Skipping UI deps (directory $UiDir\ missing or node unavailable)."
}

# ---------------------------------------------------------------------------
# Step 5 - service start stubs (env-guide.md section 1 references these)
# ---------------------------------------------------------------------------
$scriptsDir = "scripts"
if (-not (Test-Path $scriptsDir)) { New-Item -ItemType Directory -Path $scriptsDir | Out-Null }

function Write-IfMissing {
    param([string]$Path, [string]$Body)
    if (-not (Test-Path $Path)) {
        Set-Content -Path $Path -Value $Body -NoNewline -Encoding UTF8
        Write-Host "Wrote stub $Path"
    }
}

$apiSh = @'
#!/usr/bin/env bash
# Harness api service launcher (FastAPI + uvicorn, 127.0.0.1:8765)
# See env-guide.md section 1. Replaced with real launcher once F01/F02 land.
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
echo "[svc-api-start] harness.api not implemented yet -- placeholder running." >&2
while true; do sleep 3600; done
'@

$uiSh = @'
#!/usr/bin/env bash
# Harness ui-dev service launcher (Vite dev server, 127.0.0.1:5173)
# See env-guide.md section 1. Replaced with real launcher once apps/ui/ lands.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -d "apps/ui" ] && [ -f "apps/ui/package.json" ]; then
    cd apps/ui
    exec npm run dev -- --host 127.0.0.1 --port 5173
fi
echo "[svc-ui-dev-start] apps/ui/ not scaffolded yet -- placeholder running." >&2
while true; do sleep 3600; done
'@

$apiPs = @'
# Harness api service launcher (Windows). See env-guide.md section 1.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if (Test-Path ".venv\Scripts\Activate.ps1") {
    & ".venv\Scripts\Activate.ps1"
}
if (-not $env:HARNESS_HOME) { $env:HARNESS_HOME = Join-Path $HOME ".harness" }
$hasApi = $false
try { & python -c "import harness.api" 2>$null; if ($LASTEXITCODE -eq 0) { $hasApi = $true } } catch {}
if ($hasApi) {
    & uvicorn harness.api:app --host 127.0.0.1 --port 8765
} else {
    Write-Warning "[svc-api-start] harness.api not implemented yet -- placeholder running."
    while ($true) { Start-Sleep -Seconds 3600 }
}
'@

$uiPs = @'
# Harness ui-dev service launcher (Windows). See env-guide.md section 1.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if ((Test-Path "apps\ui") -and (Test-Path "apps\ui\package.json")) {
    Set-Location "apps\ui"
    & npm run dev -- --host 127.0.0.1 --port 5173
} else {
    Write-Warning "[svc-ui-dev-start] apps/ui/ not scaffolded yet -- placeholder running."
    while ($true) { Start-Sleep -Seconds 3600 }
}
'@

Write-IfMissing -Path (Join-Path $scriptsDir "svc-api-start.sh")    -Body $apiSh
Write-IfMissing -Path (Join-Path $scriptsDir "svc-ui-dev-start.sh") -Body $uiSh
Write-IfMissing -Path (Join-Path $scriptsDir "svc-api-start.ps1")    -Body $apiPs
Write-IfMissing -Path (Join-Path $scriptsDir "svc-ui-dev-start.ps1") -Body $uiPs

# ---------------------------------------------------------------------------
# Step 6 - verify
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=== Environment Check ==="
Write-Host ("python : " + (& python --version 2>&1))
Write-Host ("pip    : " + ((& pip --version 2>&1) -split "\s+")[0..1] -join " ")
if ($nodeCmd) {
    Write-Host ("node   : " + (& node --version 2>&1))
    Write-Host ("npm    : " + (& npm --version 2>&1))
} else {
    Write-Host "node   : (not installed - required for apps/ui/)"
}
foreach ($tool in @("pytest", "ruff", "black", "mypy")) {
    if (Get-Command $tool -ErrorAction SilentlyContinue) {
        $ver = (& $tool --version 2>&1 | Select-Object -First 1)
        Write-Host ("{0,-7}: {1}" -f $tool, $ver)
    }
}
Write-Host ""
Write-Host "Activate with: & $VenvDir\Scripts\Activate.ps1"
Write-Host "Environment ready."
