param(
    [Parameter(Mandatory)]
    [string]$Source
)

$ErrorActionPreference = "Stop"

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

$sourcePath = [IO.Path]::GetFullPath($Source)
$manifestPath = Join-Path $sourcePath "manifest.json"
$archivePath = Join-Path $sourcePath "lig-paddleocr-vl-1.6-images.tar.gz"
foreach ($path in @($manifestPath, $archivePath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "PaddleOCR-VL 배포 파일이 없습니다: $path" }
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.bundleFormat -ne 12) { throw "지원하지 않는 에어갭 번들 형식입니다: $($manifest.bundleFormat)" }
if (-not $manifest.paddleOcrVlIncluded -or $manifest.paddleOcrVlModel -ne "PaddleOCR-VL-1.6") {
    throw "이 번들에는 PaddleOCR-VL-1.6 선택 이미지가 없습니다."
}
if ($manifest.paddleOcrVlPipelineImage -ne "lig/paddleocr-vl-pipeline-cpu:1.6-1" -or $manifest.paddleOcrVlPipelineDevice -ne "cpu") {
    throw "PaddleOCR-VL pipeline이 CPU 전용 이미지로 고정되지 않은 번들입니다."
}
if ($manifest.paddleOcrVlPipelineImage -notin @($manifest.paddleOcrVlImages)) {
    throw "PaddleOCR-VL CPU pipeline 이미지가 manifest 이미지 목록에 없습니다."
}
$record = $manifest.files | Where-Object { $_.file -eq "lig-paddleocr-vl-1.6-images.tar.gz" } | Select-Object -First 1
if (-not $record) { throw "PaddleOCR-VL 이미지 압축파일이 manifest에 없습니다." }
if ((Get-Item -LiteralPath $archivePath).Length -ne [long]$record.bytes) { throw "PaddleOCR-VL 압축파일 크기가 manifest와 다릅니다." }
if ((Get-Sha256Hex $archivePath) -ne ([string]$record.sha256).ToLowerInvariant()) { throw "PaddleOCR-VL 압축파일 SHA-256이 manifest와 다릅니다." }

& docker load --input $archivePath
if ($LASTEXITCODE -ne 0) { throw "PaddleOCR-VL Docker 이미지를 불러오지 못했습니다." }
foreach ($image in @($manifest.paddleOcrVlImages)) {
    $expected = $manifest.paddleOcrVlImageIds.PSObject.Properties[[string]$image]
    if (-not $expected) { throw "PaddleOCR-VL 이미지 ID가 manifest에 없습니다: $image" }
    $actual = (& docker image inspect --format "{{.Id}}" $image).Trim()
    if ($LASTEXITCODE -ne 0 -or $actual -ne [string]$expected.Value) {
        throw "불러온 PaddleOCR-VL 이미지 ID가 manifest와 다릅니다: $image"
    }
}

& (Join-Path $PSScriptRoot "lig-ragflow.ps1") paddleocr-vl-start
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& (Join-Path $PSScriptRoot "lig-ragflow.ps1") paddleocr-vl-test
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
