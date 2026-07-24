$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "LIG-Deployment\airgap-import.ps1") -Source $PSScriptRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "LIG AI Knowledge Hub is running at http://127.0.0.1:8080"
Write-Host "See README.ko.md for vLLM and API key configuration."
