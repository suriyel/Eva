# Harness api service launcher (Windows). See env-guide.md §1.
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
    Write-Warning "[svc-api-start] harness.api not implemented yet — placeholder running."
    while ($true) { Start-Sleep -Seconds 3600 }
}
