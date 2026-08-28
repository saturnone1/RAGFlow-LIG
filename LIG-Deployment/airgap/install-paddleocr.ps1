$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "LIG-Deployment\paddleocr-import.ps1") -Source $PSScriptRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "일반 PaddleOCR PP-OCRv5 CPU 선택 서비스가 설치되어 실행 중입니다."
Write-Host "상태 확인: http://127.0.0.1:42316/health"
