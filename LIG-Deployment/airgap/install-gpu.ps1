$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "LIG-Deployment\airgap-import.ps1") -Source $PSScriptRoot -Device gpu
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "LIG AI Knowledge Hub GPU 구성이 실행 중입니다: http://127.0.0.1:42300"
Write-Host "장치 배치: DeepDOC=GPU | 일반 PP-OCRv5=선택 실행 CPU | PaddleOCR-VL=선택 설치 GPU"
Write-Host "공식 MCP: http://127.0.0.1:42303/mcp"
Write-Host "LIG 관리 MCP: http://127.0.0.1:42306/mcp"
Write-Host "재부팅 후 start-gpu.ps1을 사용하십시오. 자세한 내용은 INSTALL-AND-CONFIGURATION.ko.md를 참고하십시오."
