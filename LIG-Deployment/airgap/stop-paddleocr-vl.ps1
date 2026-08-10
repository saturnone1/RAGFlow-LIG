$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "LIG-Deployment\lig-ragflow.ps1") paddleocr-vl-stop
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
