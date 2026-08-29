param(
    [Parameter(Mandatory)]
    [string]$Registry,
    [switch]$IncludeGpu,
    [switch]$IncludeEmbedding,
    [switch]$IncludePaddleOcr,
    [switch]$IncludePaddleOcrVl
)

$ErrorActionPreference = "Stop"
$Registry = $Registry.Trim().TrimEnd('/')
if (-not $Registry -or $Registry -match '\s') { throw "올바른 Registry 주소를 입력하십시오." }

$images = @(
    "lig/ragflow-ui:v0.26.4-4",
    "lig/ragflow-mcp:v0.26.4-3",
    "infiniflow/ragflow:v0.26.4",
    "infiniflow/infinity:v0.7.0",
    "mysql:8.0.39",
    "pgsty/minio:RELEASE.2026-03-25T00-00-00Z",
    "valkey/valkey:8"
)
if ($IncludeGpu) { $images += "lig/ragflow-ui-gpu:v0.26.4-4" }
if ($IncludeEmbedding) { $images += @("lig/qwen3-embedding-tei:0.6b-1", "lig/qwen3-embedding-adapter:0.6b-1") }
if ($IncludePaddleOcr) { $images += "lig/paddleocr-ko:v0.26.4-4" }
if ($IncludePaddleOcrVl) {
    $images += @("lig/paddleocr-vl-pipeline-cpu:1.6-1", "lig/paddleocr-vl-vlm:1.6-2", "lig/paddleocr-vl-gateway:1.6-1")
}

foreach ($source in $images) {
    & docker image inspect $source *> $null
    if ($LASTEXITCODE -ne 0) { throw "로컬 이미지가 없습니다: $source" }
    $target = "$Registry/$source"
    & docker tag $source $target
    if ($LASTEXITCODE -ne 0) { throw "태그 생성 실패: $target" }
    & docker push $target
    if ($LASTEXITCODE -ne 0) { throw "Registry 업로드 실패: $target" }
}
Write-Host "Registry 업로드를 완료했습니다: $Registry"

