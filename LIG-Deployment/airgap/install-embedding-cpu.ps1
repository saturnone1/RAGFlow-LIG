$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "LIG-Deployment\embedding-import.ps1") -Source $PSScriptRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Qwen/Qwen3-Embedding-0.6B is running on CPU."
Write-Host "Health: http://127.0.0.1:42317/health"
Write-Host "RAGFlow provider: HuggingFace"
Write-Host "Model: Qwen/Qwen3-Embedding-0.6B"
Write-Host "Base URL from RAGFlow: http://qwen3-embedding:8080"
Write-Host "See INSTALL-AND-CONFIGURATION.ko.md before changing an existing dataset's embedding model."
