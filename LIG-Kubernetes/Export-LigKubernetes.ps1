param(
    [string]$Destination = ""
)

$ErrorActionPreference = "Stop"
if (-not (Get-Command helm -CommandType Application -ErrorAction SilentlyContinue)) {
    throw "helm을 찾을 수 없습니다."
}

if (-not $Destination) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $Destination = Join-Path $desktop ("LIG-Kubernetes-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
}

$destinationPath = [IO.Path]::GetFullPath($Destination)
$driveRoot = [IO.Path]::GetPathRoot($destinationPath)
if ($destinationPath.TrimEnd('\') -eq $driveRoot.TrimEnd('\')) {
    throw "드라이브 루트에는 내보낼 수 없습니다."
}
if (Test-Path -LiteralPath $destinationPath) {
    throw "대상 경로가 이미 존재합니다: $destinationPath"
}

& (Join-Path $PSScriptRoot "Test-LigKubernetes.ps1")

New-Item -ItemType Directory -Path $destinationPath | Out-Null
& helm package $PSScriptRoot --destination $destinationPath
if ($LASTEXITCODE -ne 0) { throw "Helm Chart 패키징 실패" }

foreach ($fileName in @(
    "README.ko.md",
    "values-airgap.example.yaml",
    "secret.example.yaml",
    "New-LigRagFlowSecret.ps1",
    "Install-LigRagFlow.ps1",
    "Push-LigImages.ps1",
    "Test-LigKubernetes.ps1"
)) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $fileName) -Destination $destinationPath
}

Write-Host "Kubernetes 이전 준비본을 생성했습니다: $destinationPath"
Write-Host "Docker Compose 에어갭 번들과 이미지는 변경하거나 다시 만들지 않았습니다."
