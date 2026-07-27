$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "LIG-Deployment\airgap-import.ps1") -Source $PSScriptRoot -Device gpu
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "LIG AI Knowledge Hub is running with NVIDIA DeepDOC and PaddleOCR acceleration at http://127.0.0.1:42300"
Write-Host "Official MCP: http://127.0.0.1:42303/mcp"
Write-Host "LIG management MCP: http://127.0.0.1:42306/mcp"
Write-Host "Use start-gpu.ps1 after a reboot. See INSTALL-AND-CONFIGURATION.ko.md for GPU and embedding configuration."
