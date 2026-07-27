param(
    [Parameter(Mandatory)]
    [string]$Source
)

$ErrorActionPreference = "Stop"
$sourcePath = [IO.Path]::GetFullPath($Source)
$manifestPath = Join-Path $sourcePath "manifest.json"
$archivePath = Join-Path $sourcePath "lig-qwen3-embedding-images-0.6b.tar.gz"

foreach ($path in @($manifestPath, $archivePath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required embedding bundle file not found: $path" }
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.bundleFormat -ne 6) { throw "Unsupported air-gap bundle format: $($manifest.bundleFormat)" }

$expectedImages = @(
    "lig/qwen3-embedding-tei:0.6b-1",
    "lig/qwen3-embedding-adapter:0.6b-1"
)
if ((@($manifest.embeddingImages | Sort-Object) -join "`n") -ne (@($expectedImages | Sort-Object) -join "`n")) {
    throw "Manifest embedding image list is missing or unsupported."
}

$archiveRecord = $manifest.files | Where-Object { $_.file -eq "lig-qwen3-embedding-images-0.6b.tar.gz" } | Select-Object -First 1
if (-not $archiveRecord) { throw "Embedding image archive is absent from the manifest." }
if ((Get-Item -LiteralPath $archivePath).Length -ne [long]$archiveRecord.bytes) { throw "Embedding archive size mismatch." }
$actualHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne ([string]$archiveRecord.sha256).ToLowerInvariant()) { throw "Embedding archive SHA-256 mismatch." }

docker load --input $archivePath
if ($LASTEXITCODE -ne 0) { throw "Embedding image docker load failed." }

foreach ($image in $expectedImages) {
    $expectedIdProperty = $manifest.embeddingImageIds.PSObject.Properties[$image]
    if (-not $expectedIdProperty) { throw "Embedding image ID is absent from the manifest: $image" }
    $actualId = (& docker image inspect --format '{{.Id}}' $image).Trim()
    if ($LASTEXITCODE -ne 0 -or $actualId -ne [string]$expectedIdProperty.Value) {
        throw "Loaded embedding image ID does not match the manifest: $image"
    }
}

$secretFile = Join-Path $PSScriptRoot ".env.secret"
if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot ".env.secret.example") -Destination $secretFile
    Write-Warning "Created LIG-Deployment\.env.secret from the example. Run install.ps1 or install-gpu.ps1 before using RAGFlow and replace its placeholder API key."
}

& (Join-Path $PSScriptRoot "lig-ragflow.ps1") embedding-start
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& (Join-Path $PSScriptRoot "lig-ragflow.ps1") embedding-test
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
