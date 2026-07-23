param(
    [Parameter(Mandatory)]
    [string]$Destination
)

$ErrorActionPreference = "Stop"
$destinationPath = [IO.Path]::GetFullPath($Destination)
$driveRoot = [IO.Path]::GetPathRoot($destinationPath)
if ($destinationPath.TrimEnd('\') -eq $driveRoot.TrimEnd('\')) { throw "A drive root cannot be used as the export destination." }
if (-not (Test-Path -LiteralPath $destinationPath)) { New-Item -ItemType Directory -Path $destinationPath | Out-Null }
if (-not (Test-Path -LiteralPath $destinationPath -PathType Container)) { throw "Destination is not a directory: $destinationPath" }

$images = @(
    "infiniflow/ragflow:v0.26.4",
    "infiniflow/infinity:v0.7.0",
    "mysql:8.0.39",
    "pgsty/minio:RELEASE.2026-03-25T00-00-00Z",
    "valkey/valkey:8",
    "ollama/ollama:0.32.0"
)
foreach ($image in $images) {
    docker image inspect $image *> $null
    if ($LASTEXITCODE -ne 0) { throw "Required image is missing: $image" }
}

$imageArchive = Join-Path $destinationPath "lig-ragflow-images-v0.26.4.tar"
docker save --output $imageArchive @images
if ($LASTEXITCODE -ne 0) { throw "docker save failed" }

$container = "lig-ragflow-ollama-1"
docker inspect $container *> $null
if ($LASTEXITCODE -ne 0) { throw "Ollama container is not running: $container" }
$containerArchive = "/tmp/lig-ollama-models.tgz"
docker exec $container tar -C /root/.ollama -czf $containerArchive .
if ($LASTEXITCODE -ne 0) { throw "Ollama model archive failed" }
try {
    docker cp "${container}:${containerArchive}" (Join-Path $destinationPath "lig-ollama-models.tgz")
    if ($LASTEXITCODE -ne 0) { throw "Ollama model copy failed" }
}
finally {
    docker exec $container rm -f $containerArchive *> $null
}

$records = Get-ChildItem -LiteralPath $destinationPath -File | ForEach-Object {
    $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
    [pscustomobject]@{ file = $_.Name; bytes = $_.Length; sha256 = $hash.Hash.ToLowerInvariant() }
}
$manifest = [pscustomobject]@{ ragflowVersion = "v0.26.4"; ollamaModel = "qwen3-embedding:0.6b"; createdAt = (Get-Date).ToString("o"); files = @($records) }
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $destinationPath "manifest.json") -Encoding UTF8
$manifest | ConvertTo-Json -Depth 5
