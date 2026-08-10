$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "LIG-Deployment\paddleocr-vl-import.ps1") -Source $PSScriptRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
