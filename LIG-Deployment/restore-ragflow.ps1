param(
    [Parameter(Mandatory)]
    [string]$Source,
    [switch]$ConfirmRestore,
    [switch]$RestoreConfiguration,
    [switch]$LeaveStopped
)

$ErrorActionPreference = "Stop"
if (-not $ConfirmRestore) { throw "복원은 기존 데이터 볼륨을 교체합니다. 확인했다면 -ConfirmRestore를 지정하십시오." }
$deploymentDirectory = $PSScriptRoot
$launcher = Join-Path $deploymentDirectory "lig-ragflow.ps1"
$sourcePath = [IO.Path]::GetFullPath($Source)
$manifestPath = Join-Path $sourcePath "manifest.json"
$dockerExecutable = (Get-Command docker -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "manifest.json이 없습니다: $sourcePath" }
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.FormatVersion -ne 1) { throw "지원하지 않는 백업 형식입니다: $($manifest.FormatVersion)" }
$allowedFiles = @("mysql_data.tar.gz", "minio_data.tar.gz", "infinity_data.tar.gz", "redis_data.tar.gz", ".env.lig", ".env.secret")
foreach ($file in $manifest.Files) {
    if ([IO.Path]::GetFileName($file.Name) -ne $file.Name -or $file.Name -notin $allowedFiles) {
        throw "허용되지 않은 백업 파일 이름입니다: $($file.Name)"
    }
    $path = Join-Path $sourcePath $file.Name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "백업 파일이 없습니다: $($file.Name)" }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $file.Sha256) { throw "백업 무결성 검증 실패: $($file.Name)" }
}
foreach ($requiredArchive in $allowedFiles[0..3]) {
    if (-not ($manifest.Files.Name -contains $requiredArchive)) { throw "필수 백업 파일이 manifest에 없습니다: $requiredArchive" }
}

function Get-EnvValue([string]$Path, [string]$Name) {
    $line = Get-Content -LiteralPath $Path | Where-Object { $_ -match "^$([regex]::Escape($Name))=" } | Select-Object -Last 1
    if (-not $line) { return $null }
    return ($line -split '=', 2)[1].Trim()
}
$runtimeImage = Get-EnvValue (Join-Path $deploymentDirectory ".env.lig") "RAGFLOW_IMAGE"
if (-not $runtimeImage) { throw "현재 배포의 RAGFLOW_IMAGE 설정을 찾을 수 없습니다." }

function Invoke-Docker([string[]]$Arguments) {
    & $dockerExecutable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "docker failed with exit code $LASTEXITCODE" }
}

& $launcher stop
if ($LASTEXITCODE -ne 0) { throw "RAGFlow 정지에 실패했습니다." }
$volumes = @("mysql_data", "minio_data", "infinity_data", "redis_data")
foreach ($suffix in $volumes) {
    $volume = "lig-ragflow_$suffix"
    & $dockerExecutable volume inspect $volume *> $null
    if ($LASTEXITCODE -ne 0) { Invoke-Docker @("volume", "create", $volume) }
    Invoke-Docker @(
        "run", "--rm", "--entrypoint", "/ragflow/.venv/bin/python",
        "--mount", "type=volume,source=$volume,target=/target",
        "--mount", "type=bind,source=$sourcePath,target=/backup,readonly",
        $runtimeImage, "-m", "lig_runtime.volume_archive", "restore", "/backup/$suffix.tar.gz", "/target"
    )
}
if ($RestoreConfiguration) {
    Copy-Item -LiteralPath (Join-Path $sourcePath ".env.lig") -Destination (Join-Path $deploymentDirectory ".env.lig") -Force
    $backupSecret = Join-Path $sourcePath ".env.secret"
    if (Test-Path -LiteralPath $backupSecret -PathType Leaf) {
        Copy-Item -LiteralPath $backupSecret -Destination (Join-Path $deploymentDirectory ".env.secret") -Force
    }
}
Write-Host "백업 데이터 복원이 완료됐습니다: $sourcePath"
if (-not $LeaveStopped) { & $launcher start }
