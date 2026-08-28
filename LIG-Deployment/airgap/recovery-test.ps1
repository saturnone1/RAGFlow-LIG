$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "LIG-Deployment\lig-ragflow.ps1") recovery-test
