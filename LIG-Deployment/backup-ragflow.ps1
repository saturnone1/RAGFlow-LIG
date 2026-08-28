param(
    [string]$Destination,
    [switch]$LeaveStopped
)

$ErrorActionPreference = "Stop"
$deploymentDirectory = $PSScriptRoot
$launcher = Join-Path $deploymentDirectory "lig-ragflow.ps1"
$envFile = Join-Path $deploymentDirectory ".env.lig"
$secretFile = Join-Path $deploymentDirectory ".env.secret"
$dockerExecutable = (Get-Command docker -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source

function Get-EnvValue([string]$Path, [string]$Name) {
    $line = Get-Content -LiteralPath $Path | Where-Object { $_ -match "^$([regex]::Escape($Name))=" } | Select-Object -Last 1
    if (-not $line) { return $null }
    return ($line -split '=', 2)[1].Trim()
}

function Invoke-Docker([string[]]$Arguments) {
    & $dockerExecutable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "docker failed with exit code $LASTEXITCODE" }
}

if (-not $Destination) {
    $root = Join-Path ([Environment]::GetFolderPath("Desktop")) "LIG-RAGFlow-Backups"
    $Destination = Join-Path $root (Get-Date -Format "yyyyMMdd-HHmmss")
}
$destinationPath = [IO.Path]::GetFullPath($Destination)
$driveRoot = [IO.Path]::GetPathRoot($destinationPath)
if ($destinationPath.TrimEnd('\') -eq $driveRoot.TrimEnd('\')) { throw "드라이브 루트에는 백업할 수 없습니다." }
if (Test-Path -LiteralPath $destinationPath) {
    if (@(Get-ChildItem -LiteralPath $destinationPath -Force).Count) { throw "백업 대상 폴더는 비어 있어야 합니다: $destinationPath" }
} else {
    New-Item -ItemType Directory -Path $destinationPath | Out-Null
}

$image = Get-EnvValue $envFile "RAGFLOW_IMAGE"
if (-not $image) { throw "RAGFLOW_IMAGE 설정을 찾을 수 없습니다." }
$volumes = @("mysql_data", "minio_data", "infinity_data", "redis_data")
$wasRunning = @(& $dockerExecutable ps --filter "label=com.docker.compose.project=lig-ragflow" --format "{{.Names}}")
if ($LASTEXITCODE -ne 0) { throw "Docker 상태를 확인할 수 없습니다." }

try {
    & $launcher stop
    if ($LASTEXITCODE -ne 0) { throw "RAGFlow 정지에 실패했습니다." }
    foreach ($suffix in $volumes) {
        $volume = "lig-ragflow_$suffix"
        & $dockerExecutable volume inspect $volume *> $null
        if ($LASTEXITCODE -ne 0) { throw "필수 볼륨이 없습니다: $volume" }
        Invoke-Docker @(
            "run", "--rm", "--entrypoint", "/ragflow/.venv/bin/python",
            "--mount", "type=volume,source=$volume,target=/source,readonly",
            "--mount", "type=bind,source=$destinationPath,target=/backup",
            $image, "-m", "lig_runtime.volume_archive", "pack", "/source", "/backup/$suffix.tar.gz"
        )
    }
    Copy-Item -LiteralPath $envFile -Destination (Join-Path $destinationPath ".env.lig")
    if (Test-Path -LiteralPath $secretFile -PathType Leaf) {
        Copy-Item -LiteralPath $secretFile -Destination (Join-Path $destinationPath ".env.secret")
    }
    $files = @(Get-ChildItem -LiteralPath $destinationPath -File | Sort-Object Name | ForEach-Object {
        [pscustomobject]@{ Name = $_.Name; Bytes = $_.Length; Sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
    })
    [pscustomobject]@{
        FormatVersion = 1
        CreatedAt = (Get-Date).ToString("o")
        Image = $image
        Project = "lig-ragflow"
        Files = $files
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $destinationPath "manifest.json") -Encoding UTF8
    Write-Host "무결성 해시를 포함한 일관된 백업을 만들었습니다: $destinationPath"
    Write-Warning "이 폴더에는 .env.secret이 포함될 수 있으므로 접근 권한을 제한하십시오."
}
finally {
    if (-not $LeaveStopped -and $wasRunning.Count) {
        & $launcher start
        if ($wasRunning -match 'paddleocr-cpu') { & $launcher paddleocr-start }
        if ($wasRunning -match 'qwen3-embedding') { & $launcher embedding-start }
        if ($wasRunning -match 'paddleocr-vl') { & $launcher paddleocr-vl-start }
    }
}
