param(
    [Parameter(Mandatory)]
    [string]$Destination,
    [string]$ExistingImageArchive
)

$ErrorActionPreference = "Stop"
$destinationPath = [IO.Path]::GetFullPath($Destination)
$deploymentDirectory = $PSScriptRoot
$workspaceDirectory = Split-Path $deploymentDirectory -Parent
$upstreamDockerDirectory = Join-Path $workspaceDirectory "RAGFlow\docker"
$bundleTemplateDirectory = Join-Path $deploymentDirectory "airgap"
$driveRoot = [IO.Path]::GetPathRoot($destinationPath)
if ($destinationPath.TrimEnd('\') -eq $driveRoot.TrimEnd('\')) { throw "A drive root cannot be used as the export destination." }
if (-not (Test-Path -LiteralPath $destinationPath)) { New-Item -ItemType Directory -Path $destinationPath | Out-Null }
if (-not (Test-Path -LiteralPath $destinationPath -PathType Container)) { throw "Destination is not a directory: $destinationPath" }
if (@(Get-ChildItem -LiteralPath $destinationPath -Force).Count -gt 0) {
    throw "Export destination must be empty to prevent stale files or secrets from entering the bundle: $destinationPath"
}

# Copy only the files required by the fixed Infinity CPU/GPU deployment. Secrets
# and source code are intentionally excluded so the result is a portable runtime bundle.
$bundleFiles = @(
    @{ Source = (Join-Path $bundleTemplateDirectory "install.ps1"); Target = "install.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "install-gpu.ps1"); Target = "install-gpu.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "install-embedding-cpu.ps1"); Target = "install-embedding-cpu.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "start.ps1"); Target = "start.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "start-gpu.ps1"); Target = "start-gpu.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "start-embedding-cpu.ps1"); Target = "start-embedding-cpu.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "stop.ps1"); Target = "stop.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "stop-embedding.ps1"); Target = "stop-embedding.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "status.ps1"); Target = "status.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "test-embedding.ps1"); Target = "test-embedding.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "diagnostics.ps1"); Target = "diagnostics.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "diagnostics-gpu.ps1"); Target = "diagnostics-gpu.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "logs.ps1"); Target = "logs.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "README.ko.md"); Target = "README.ko.md" },
    @{ Source = (Join-Path $bundleTemplateDirectory "INSTALL-AND-CONFIGURATION.ko.md"); Target = "INSTALL-AND-CONFIGURATION.ko.md" },
    @{ Source = (Join-Path $deploymentDirectory "airgap-import.ps1"); Target = "LIG-Deployment\airgap-import.ps1" },
    @{ Source = (Join-Path $deploymentDirectory "embedding-import.ps1"); Target = "LIG-Deployment\embedding-import.ps1" },
    @{ Source = (Join-Path $deploymentDirectory "lig-ragflow.ps1"); Target = "LIG-Deployment\lig-ragflow.ps1" },
    @{ Source = (Join-Path $deploymentDirectory "docker-compose.lig.yml"); Target = "LIG-Deployment\docker-compose.lig.yml" },
    @{ Source = (Join-Path $deploymentDirectory ".env.lig"); Target = "LIG-Deployment\.env.lig" },
    @{ Source = (Join-Path $deploymentDirectory ".env.secret.example"); Target = "LIG-Deployment\.env.secret.example" },
    @{ Source = (Join-Path $upstreamDockerDirectory ".env"); Target = "RAGFlow\docker\.env" },
    @{ Source = (Join-Path $upstreamDockerDirectory "docker-compose.yml"); Target = "RAGFlow\docker\docker-compose.yml" },
    @{ Source = (Join-Path $upstreamDockerDirectory "docker-compose-base.yml"); Target = "RAGFlow\docker\docker-compose-base.yml" },
    @{ Source = (Join-Path $upstreamDockerDirectory "entrypoint.sh"); Target = "RAGFlow\docker\entrypoint.sh" },
    @{ Source = (Join-Path $upstreamDockerDirectory "service_conf.yaml.template"); Target = "RAGFlow\docker\service_conf.yaml.template" },
    @{ Source = (Join-Path $upstreamDockerDirectory "infinity_conf.toml"); Target = "RAGFlow\docker\infinity_conf.toml" },
    @{ Source = (Join-Path $upstreamDockerDirectory "init.sql"); Target = "RAGFlow\docker\init.sql" }
)
foreach ($bundleFile in $bundleFiles) {
    if (-not (Test-Path -LiteralPath $bundleFile.Source -PathType Leaf)) {
        throw "Required bundle source file is missing: $($bundleFile.Source)"
    }
    $target = Join-Path $destinationPath $bundleFile.Target
    $targetDirectory = Split-Path $target -Parent
    if (-not (Test-Path -LiteralPath $targetDirectory)) {
        New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
    }
    Copy-Item -LiteralPath $bundleFile.Source -Destination $target -Force
}

$images = @(
    "lig/ragflow-ui:v0.26.4-1",
    "lig/ragflow-ui-gpu:v0.26.4-1",
    "lig/ragflow-mcp:v0.26.4-1",
    "lig/paddleocr-ko:v0.26.4-1",
    "lig/paddleocr-ko-gpu:v0.26.4-1",
    "infiniflow/ragflow:v0.26.4",
    "infiniflow/infinity:v0.7.0",
    "mysql:8.0.39",
    "pgsty/minio:RELEASE.2026-03-25T00-00-00Z",
    "valkey/valkey:8"
)
foreach ($image in $images) {
    docker image inspect $image *> $null
    if ($LASTEXITCODE -ne 0) { throw "Required image is missing: $image" }
}
$imageIds = [ordered]@{}
foreach ($image in $images) {
    $imageIds[$image] = (& docker image inspect --format '{{.Id}}' $image).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $imageIds[$image]) { throw "Could not resolve image ID: $image" }
}

$uncompressedArchive = Join-Path $destinationPath "lig-ragflow-images-v0.26.4.tar"
$imageArchive = Join-Path $destinationPath "lig-ragflow-images-v0.26.4.tar.gz"
if ($ExistingImageArchive) {
    $existingArchivePath = [IO.Path]::GetFullPath($ExistingImageArchive)
    if (-not (Test-Path -LiteralPath $existingArchivePath -PathType Leaf)) {
        throw "Existing image archive not found: $existingArchivePath"
    }
    if ([IO.Path]::GetExtension($existingArchivePath) -ne ".gz") {
        throw "Existing image archive must be a .tar.gz file: $existingArchivePath"
    }
    $existingManifestPath = Join-Path (Split-Path $existingArchivePath -Parent) "manifest.json"
    if (-not (Test-Path -LiteralPath $existingManifestPath -PathType Leaf)) {
        throw "The existing archive must have a sibling manifest.json: $existingManifestPath"
    }
    $existingManifest = Get-Content -LiteralPath $existingManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $expectedImages = @($images | Sort-Object)
    $archivedImages = @($existingManifest.images | Sort-Object)
    if (($expectedImages -join "`n") -ne ($archivedImages -join "`n")) {
        throw "Existing archive image list does not match this export."
    }
    if (-not $existingManifest.imageIds) {
        throw "Existing manifest has no image IDs and cannot be safely reused."
    }
    foreach ($image in $images) {
        $archivedIdProperty = $existingManifest.imageIds.PSObject.Properties[$image]
        if (-not $archivedIdProperty -or [string]$archivedIdProperty.Value -ne [string]$imageIds[$image]) {
            throw "Existing archive image ID does not match the current image: $image"
        }
    }
    $archiveRecord = $existingManifest.files | Where-Object { $_.file -eq "lig-ragflow-images-v0.26.4.tar.gz" } | Select-Object -First 1
    if (-not $archiveRecord) { throw "Existing manifest has no Docker image archive record." }
    $archiveItem = Get-Item -LiteralPath $existingArchivePath
    if ($archiveItem.Length -ne [long]$archiveRecord.bytes) { throw "Existing image archive size does not match its manifest." }
    $archiveHash = (Get-FileHash -LiteralPath $existingArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($archiveHash -ne ([string]$archiveRecord.sha256).ToLowerInvariant()) {
        throw "Existing image archive SHA-256 does not match its manifest."
    }
    Write-Host "Reusing validated Docker image archive: $existingArchivePath"
    Copy-Item -LiteralPath $existingArchivePath -Destination $imageArchive
}
else {
    docker save --output $uncompressedArchive @images
    if ($LASTEXITCODE -ne 0) { throw "docker save failed" }

    Write-Host "Compressing Docker image archive with gzip..."
    $inputStream = $null
    $outputStream = $null
    $gzipStream = $null
    $compressionError = $null
    try {
        $inputStream = [IO.File]::OpenRead($uncompressedArchive)
        $outputStream = [IO.File]::Create($imageArchive)
        $gzipStream = [IO.Compression.GZipStream]::new(
            $outputStream,
            [IO.Compression.CompressionLevel]::Optimal,
            $false
        )
        $inputStream.CopyTo($gzipStream, 1MB)
    }
    catch {
        $compressionError = $_
    }
    finally {
        if ($null -ne $gzipStream) { $gzipStream.Dispose() }
        if ($null -ne $outputStream) { $outputStream.Dispose() }
        if ($null -ne $inputStream) { $inputStream.Dispose() }
        if (Test-Path -LiteralPath $uncompressedArchive) { Remove-Item -LiteralPath $uncompressedArchive -Force }
    }
    if ($null -ne $compressionError) {
        if (Test-Path -LiteralPath $imageArchive) { Remove-Item -LiteralPath $imageArchive -Force }
        throw $compressionError
    }
}

$embeddingImages = @(
    "lig/qwen3-embedding-tei:0.6b-1",
    "lig/qwen3-embedding-adapter:0.6b-1"
)
$embeddingImageIds = [ordered]@{}
foreach ($image in $embeddingImages) {
    docker image inspect $image *> $null
    if ($LASTEXITCODE -ne 0) { throw "Required optional embedding image is missing: $image" }
    $embeddingImageIds[$image] = (& docker image inspect --format '{{.Id}}' $image).Trim()
}
$embeddingTar = Join-Path $destinationPath "lig-qwen3-embedding-images-0.6b.tar"
$embeddingArchive = Join-Path $destinationPath "lig-qwen3-embedding-images-0.6b.tar.gz"
docker save --output $embeddingTar @embeddingImages
if ($LASTEXITCODE -ne 0) { throw "Embedding docker save failed" }
Write-Host "Compressing optional Qwen3 embedding image archive with gzip..."
$embeddingInput = $null
$embeddingOutput = $null
$embeddingGzip = $null
try {
    $embeddingInput = [IO.File]::OpenRead($embeddingTar)
    $embeddingOutput = [IO.File]::Create($embeddingArchive)
    $embeddingGzip = [IO.Compression.GZipStream]::new($embeddingOutput, [IO.Compression.CompressionLevel]::Optimal, $false)
    $embeddingInput.CopyTo($embeddingGzip, 1MB)
}
finally {
    if ($null -ne $embeddingGzip) { $embeddingGzip.Dispose() }
    if ($null -ne $embeddingOutput) { $embeddingOutput.Dispose() }
    if ($null -ne $embeddingInput) { $embeddingInput.Dispose() }
    if (Test-Path -LiteralPath $embeddingTar) { Remove-Item -LiteralPath $embeddingTar -Force }
}

$destinationPrefix = $destinationPath.TrimEnd('\') + '\'
$records = Get-ChildItem -LiteralPath $destinationPath -File -Recurse | Where-Object {
    $_.Name -ne "manifest.json"
} | Sort-Object FullName | ForEach-Object {
    $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
    $relativePath = $_.FullName.Substring($destinationPrefix.Length).Replace('\', '/')
    [pscustomobject]@{ file = $relativePath; bytes = $_.Length; sha256 = $hash.Hash.ToLowerInvariant() }
}
$manifest = [pscustomobject]@{
    bundleFormat = 7
    ragflowVersion = "v0.26.4"
    uiImage = "lig/ragflow-ui:v0.26.4-1"
    gpuUiImage = "lig/ragflow-ui-gpu:v0.26.4-1"
    mcpImage = "lig/ragflow-mcp:v0.26.4-1"
    ocrImage = "lig/paddleocr-ko:v0.26.4-1"
    gpuOcrImage = "lig/paddleocr-ko-gpu:v0.26.4-1"
    images = @($images)
    imageIds = $imageIds
    embeddingImages = @($embeddingImages)
    embeddingImageIds = $embeddingImageIds
    embeddingModel = "Qwen/Qwen3-Embedding-0.6B"
    embeddingModelRevision = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
    embeddingRuntime = "TEI cpu-1.9"
    createdAt = (Get-Date).ToString("o")
    files = @($records)
}
$manifestPath = Join-Path $destinationPath "manifest.json"
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
$manifest | ConvertTo-Json -Depth 5
