param(
    [Parameter(Mandatory)]
    [string]$Destination,

    [switch]$IncludeOllama
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

# Copy only the files required by the fixed Infinity/CPU deployment. Secrets and
# source code are intentionally excluded so the result is a portable runtime bundle.
$bundleFiles = @(
    @{ Source = (Join-Path $bundleTemplateDirectory "install.ps1"); Target = "install.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "start.ps1"); Target = "start.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "stop.ps1"); Target = "stop.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "status.ps1"); Target = "status.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "diagnostics.ps1"); Target = "diagnostics.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "logs.ps1"); Target = "logs.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "README.ko.md"); Target = "README.ko.md" },
    @{ Source = (Join-Path $deploymentDirectory "airgap-import.ps1"); Target = "LIG-Deployment\airgap-import.ps1" },
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
    "lig/ragflow-mcp:v0.26.4-1",
    "infiniflow/ragflow:v0.26.4",
    "infiniflow/infinity:v0.7.0",
    "mysql:8.0.39",
    "pgsty/minio:RELEASE.2026-03-25T00-00-00Z",
    "valkey/valkey:8"
)
if ($IncludeOllama) { $images += "ollama/ollama:0.32.0" }
foreach ($image in $images) {
    docker image inspect $image *> $null
    if ($LASTEXITCODE -ne 0) { throw "Required image is missing: $image" }
}

$uncompressedArchive = Join-Path $destinationPath "lig-ragflow-images-v0.26.4.tar"
$imageArchive = Join-Path $destinationPath "lig-ragflow-images-v0.26.4.tar.gz"
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

if ($IncludeOllama) {
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
}
else {
    $unusedModelArchive = Join-Path $destinationPath "lig-ollama-models.tgz"
    if (Test-Path -LiteralPath $unusedModelArchive -PathType Leaf) {
        Remove-Item -LiteralPath $unusedModelArchive -Force
    }
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
    bundleFormat = 3
    ragflowVersion = "v0.26.4"
    uiImage = "lig/ragflow-ui:v0.26.4-1"
    mcpImage = "lig/ragflow-mcp:v0.26.4-1"
    images = @($images)
    includesOllama = [bool]$IncludeOllama
    ollamaModel = if ($IncludeOllama) { "qwen3-embedding:0.6b" } else { $null }
    createdAt = (Get-Date).ToString("o")
    files = @($records)
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $destinationPath "manifest.json") -Encoding UTF8
$manifest | ConvertTo-Json -Depth 5
