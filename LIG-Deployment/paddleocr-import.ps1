param(
    [Parameter(Mandatory)]
    [string]$Source
)

$ErrorActionPreference = "Stop"
$dockerExecutable = (Get-Command docker -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source

function Get-Sha256Hex([string]$Path) {
    $stream = $null
    $sha256 = $null
    try {
        $stream = [IO.File]::OpenRead($Path)
        $sha256 = [Security.Cryptography.SHA256]::Create()
        return ([BitConverter]::ToString($sha256.ComputeHash($stream))).Replace("-", "").ToLowerInvariant()
    }
    finally {
        if ($null -ne $sha256) { $sha256.Dispose() }
        if ($null -ne $stream) { $stream.Dispose() }
    }
}

function Invoke-DockerCapture([string[]]$Arguments, [switch]$AllowFailure) {
    $previous = $ErrorActionPreference
    $exitCode = 1
    $output = @()
    try {
        $ErrorActionPreference = "Continue"
        $output = @(& $dockerExecutable @Arguments 2>&1 | ForEach-Object { $_.ToString() })
        $exitCode = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $previous }
    if ($exitCode -ne 0 -and -not $AllowFailure) { throw "docker failed with exit code $exitCode" }
    return [pscustomobject]@{ ExitCode = $exitCode; Lines = $output }
}

$sourcePath = [IO.Path]::GetFullPath($Source)
$manifestPath = Join-Path $sourcePath "manifest.json"
$archivePath = Join-Path $sourcePath "lig-paddleocr-images-v0.26.4.tar.gz"
foreach ($path in @($manifestPath, $archivePath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "PaddleOCR 선택 설치 파일이 없습니다: $path" }
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.bundleFormat -ne 13) { throw "지원하지 않는 에어갭 번들 형식입니다: $($manifest.bundleFormat)" }
if (-not $manifest.paddleOcrIncluded -or $manifest.ocrImage -ne "lig/paddleocr-ko:v0.26.4-4") {
    throw "이 번들에는 일반 PaddleOCR 선택 이미지가 없습니다."
}
$expectedImages = @("lig/paddleocr-ko:v0.26.4-4")
if ((@($manifest.paddleOcrImages | Sort-Object) -join "`n") -ne ($expectedImages -join "`n")) {
    throw "PaddleOCR 이미지 목록이 올바르지 않습니다."
}
$record = $manifest.files | Where-Object { $_.file -eq "lig-paddleocr-images-v0.26.4.tar.gz" } | Select-Object -First 1
if (-not $record) { throw "PaddleOCR 이미지 압축파일이 manifest에 없습니다." }
if ((Get-Item -LiteralPath $archivePath).Length -ne [long]$record.bytes) { throw "PaddleOCR 압축파일 크기가 manifest와 다릅니다." }
if ((Get-Sha256Hex $archivePath) -ne ([string]$record.sha256).ToLowerInvariant()) { throw "PaddleOCR 압축파일 SHA-256이 manifest와 다릅니다." }

$load = Invoke-DockerCapture -Arguments @("load", "--input", $archivePath)
$load.Lines | ForEach-Object { Write-Host $_ }
foreach ($image in $expectedImages) {
    $expectedId = $manifest.paddleOcrImageIds.PSObject.Properties[$image]
    if (-not $expectedId) { throw "PaddleOCR 이미지 ID가 manifest에 없습니다: $image" }
    $inspect = Invoke-DockerCapture -Arguments @("image", "inspect", "--format", "{{.Id}}", $image) -AllowFailure
    $actualId = ([string]($inspect.Lines | Where-Object { $_ -match '^sha256:[0-9a-fA-F]{64}$' } | Select-Object -Last 1)).Trim()
    if ($inspect.ExitCode -ne 0 -or $actualId -ne [string]$expectedId.Value) {
        throw "불러온 PaddleOCR 이미지 ID가 manifest와 다릅니다: $image"
    }
}

& (Join-Path $PSScriptRoot "lig-ragflow.ps1") paddleocr-start
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& (Join-Path $PSScriptRoot "lig-ragflow.ps1") paddleocr-test
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
