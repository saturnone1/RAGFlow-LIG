$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "LIG-Deployment\lig-ragflow.ps1") paddleocr-vl-start
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
