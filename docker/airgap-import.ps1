param(
    [Parameter(Mandatory)]
    [string]$Source
)

$ErrorActionPreference = "Stop"
$sourcePath = [IO.Path]::GetFullPath($Source)
if (-not (Test-Path -LiteralPath $sourcePath -PathType Container)) { throw "Source directory not found: $sourcePath" }
$imageArchive = Join-Path $sourcePath "lig-ragflow-images-v0.26.4.tar"
$modelArchive = Join-Path $sourcePath "lig-ollama-models.tgz"
$manifestPath = Join-Path $sourcePath "manifest.json"
foreach ($file in @($imageArchive, $modelArchive, $manifestPath)) { if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Required archive not found: $file" } }

$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($file in @($imageArchive, $modelArchive)) {
    $name = [IO.Path]::GetFileName($file)
    $record = @($manifest.files | Where-Object file -eq $name)[0]
    if (-not $record) { throw "Manifest entry not found: $name" }
    $actual = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne ([string]$record.sha256).ToLowerInvariant()) { throw "SHA-256 mismatch: $name" }
}
Write-Host "Air-gap archive SHA-256 validation passed."

docker load --input $imageArchive
if ($LASTEXITCODE -ne 0) { throw "docker load failed" }

& (Join-Path $PSScriptRoot "lig-ragflow.ps1") start
if ($LASTEXITCODE -ne 0) { throw "RAGFlow start failed" }

$container = "lig-ragflow-ollama-1"
$containerArchive = "/tmp/lig-ollama-models.tgz"
docker cp $modelArchive "${container}:${containerArchive}"
if ($LASTEXITCODE -ne 0) { throw "Ollama model copy failed" }
try {
    docker exec $container tar -C /root/.ollama -xzf $containerArchive
    if ($LASTEXITCODE -ne 0) { throw "Ollama model restore failed" }
}
finally {
    docker exec $container rm -f $containerArchive *> $null
}
docker exec $container ollama show qwen3-embedding:0.6b
if ($LASTEXITCODE -ne 0) { throw "Restored embedding model validation failed" }
