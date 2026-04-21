# Harness ui-dev service launcher (Windows). See env-guide.md §1.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if ((Test-Path "apps\ui") -and (Test-Path "apps\ui\package.json")) {
    Set-Location "apps\ui"
    & npm run dev -- --host 127.0.0.1 --port 5173
} else {
    Write-Warning "[svc-ui-dev-start] apps/ui/ not scaffolded yet — placeholder running."
    while ($true) { Start-Sleep -Seconds 3600 }
}
