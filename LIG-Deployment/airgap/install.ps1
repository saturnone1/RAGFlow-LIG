$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "LIG-Deployment\airgap-import.ps1") -Source $PSScriptRoot -Device cpu
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "LIG AI Knowledge Hub is running at http://127.0.0.1:42300"
Write-Host "Official MCP: http://127.0.0.1:42303/mcp"
Write-Host "LIG management MCP: http://127.0.0.1:42306/mcp"
Write-Host "See README.ko.md for vLLM and API key configuration."
