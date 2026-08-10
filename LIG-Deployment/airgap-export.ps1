param(
    [Parameter(Mandatory)]
    [string]$Destination,
    [string]$ExistingImageArchive,
    [switch]$IncludeGpu,
    [switch]$IncludeEmbedding,
    [switch]$IncludePaddleOcrVl
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

function Invoke-Docker([string[]]$Arguments) {
    $previous = $ErrorActionPreference
    $exitCode = 1
    try {
        $ErrorActionPreference = "Continue"
        & docker @Arguments 2>&1 | ForEach-Object { Write-Host $_ }
        $exitCode = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previous }
    if ($exitCode -ne 0) { throw "docker failed with exit code $exitCode" }
}

function Invoke-DockerCapture([string[]]$Arguments, [switch]$AllowFailure) {
    $previous = $ErrorActionPreference
    $exitCode = 1
    $output = @()
    try {
        $ErrorActionPreference = "Continue"
        $output = @(& docker @Arguments 2>&1 | ForEach-Object { $_.ToString() })
        $exitCode = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previous }
    if ($exitCode -ne 0 -and -not $AllowFailure) { throw "docker failed with exit code $exitCode" }
    return [pscustomobject]@{ ExitCode = $exitCode; Lines = $output }
}
$destinationPath = [IO.Path]::GetFullPath($Destination)
if ($IncludePaddleOcrVl -and -not $IncludeGpu) {
    throw "PaddleOCR-VL-1.6 공식 오프라인 구성은 NVIDIA GPU용입니다. -IncludeGpu도 함께 지정하십시오."
}
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

# 고정된 Infinity CPU/GPU 배포에 필요한 파일만 복사합니다. 휴대 가능한 실행
# 번들이 되도록 비밀값과 소스 코드는 포함하지 않습니다.
$bundleFiles = @(
    @{ Source = (Join-Path $bundleTemplateDirectory "install.ps1"); Target = "install.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "install-gpu.ps1"); Target = "install-gpu.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "install-embedding-cpu.ps1"); Target = "install-embedding-cpu.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "install-paddleocr-vl.ps1"); Target = "install-paddleocr-vl.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "start.ps1"); Target = "start.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "start-gpu.ps1"); Target = "start-gpu.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "start-embedding-cpu.ps1"); Target = "start-embedding-cpu.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "start-paddleocr-vl.ps1"); Target = "start-paddleocr-vl.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "stop.ps1"); Target = "stop.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "stop-embedding.ps1"); Target = "stop-embedding.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "stop-paddleocr-vl.ps1"); Target = "stop-paddleocr-vl.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "status.ps1"); Target = "status.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "test-embedding.ps1"); Target = "test-embedding.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "test-paddleocr-vl.ps1"); Target = "test-paddleocr-vl.ps1" },
    @{ Source = (Join-Path $deploymentDirectory "verify-cpu-images.ps1"); Target = "verify-cpu-images.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "diagnostics.ps1"); Target = "diagnostics.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "diagnostics-gpu.ps1"); Target = "diagnostics-gpu.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "logs.ps1"); Target = "logs.ps1" },
    @{ Source = (Join-Path $bundleTemplateDirectory "README.ko.md"); Target = "README.ko.md" },
    @{ Source = (Join-Path $bundleTemplateDirectory "INSTALL-AND-CONFIGURATION.ko.md"); Target = "INSTALL-AND-CONFIGURATION.ko.md" },
    @{ Source = (Join-Path $deploymentDirectory "DOCUMENT-COMPATIBILITY.ko.md"); Target = "DOCUMENT-COMPATIBILITY.ko.md" },
    @{ Source = (Join-Path $deploymentDirectory "airgap-import.ps1"); Target = "LIG-Deployment\airgap-import.ps1" },
    @{ Source = (Join-Path $deploymentDirectory "embedding-import.ps1"); Target = "LIG-Deployment\embedding-import.ps1" },
    @{ Source = (Join-Path $deploymentDirectory "paddleocr-vl-import.ps1"); Target = "LIG-Deployment\paddleocr-vl-import.ps1" },
    @{ Source = (Join-Path $deploymentDirectory "lig-ragflow.ps1"); Target = "LIG-Deployment\lig-ragflow.ps1" },
    @{ Source = (Join-Path $deploymentDirectory "rotate-document-password-key.ps1"); Target = "LIG-Deployment\rotate-document-password-key.ps1" },
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
    "lig/ragflow-ui:v0.26.4-3",
    "lig/ragflow-mcp:v0.26.4-3",
    "lig/paddleocr-ko:v0.26.4-3",
    "infiniflow/ragflow:v0.26.4",
    "infiniflow/infinity:v0.7.0",
    "mysql:8.0.39",
    "pgsty/minio:RELEASE.2026-03-25T00-00-00Z",
    "valkey/valkey:8"
)
if ($IncludeGpu) {
    $images += @("lig/ragflow-ui-gpu:v0.26.4-3", "lig/paddleocr-ko-gpu:v0.26.4-3")
}
foreach ($image in $images) {
    $inspect = Invoke-DockerCapture -Arguments @("image", "inspect", "--format", "{{.Id}}", $image) -AllowFailure
    if ($inspect.ExitCode -ne 0) { throw "Required image is missing: $image" }
}
$imageIds = [ordered]@{}
foreach ($image in $images) {
    $inspect = Invoke-DockerCapture -Arguments @("image", "inspect", "--format", "{{.Id}}", $image) -AllowFailure
    $imageIds[$image] = ([string]($inspect.Lines | Where-Object { $_ -match '^sha256:[0-9a-fA-F]{64}$' } | Select-Object -Last 1)).Trim()
    if ($inspect.ExitCode -ne 0 -or -not $imageIds[$image]) { throw "Could not resolve image ID: $image" }
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
    if ($existingManifest.bundleFormat -ne 9) {
        throw "Existing image archive uses unsupported bundle format: $($existingManifest.bundleFormat)"
    }
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
    $archiveHash = Get-Sha256Hex $existingArchivePath
    if ($archiveHash -ne ([string]$archiveRecord.sha256).ToLowerInvariant()) {
        throw "Existing image archive SHA-256 does not match its manifest."
    }
    Write-Host "Reusing validated Docker image archive: $existingArchivePath"
    Copy-Item -LiteralPath $existingArchivePath -Destination $imageArchive
}
else {
    Invoke-Docker (@("save", "--output", $uncompressedArchive) + $images)

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

$embeddingImages = @()
$embeddingImageIds = [ordered]@{}
if ($IncludeEmbedding) {
    $embeddingImages = @(
    "lig/qwen3-embedding-tei:0.6b-1",
    "lig/qwen3-embedding-adapter:0.6b-1"
    )
    foreach ($image in $embeddingImages) {
        $inspect = Invoke-DockerCapture -Arguments @("image", "inspect", "--format", "{{.Id}}", $image) -AllowFailure
        if ($inspect.ExitCode -ne 0) { throw "Requested optional embedding image is missing: $image" }
        $embeddingImageIds[$image] = ([string]($inspect.Lines | Where-Object { $_ -match '^sha256:[0-9a-fA-F]{64}$' } | Select-Object -Last 1)).Trim()
        if (-not $embeddingImageIds[$image]) { throw "Could not resolve optional embedding image ID: $image" }
    }
    $embeddingTar = Join-Path $destinationPath "lig-qwen3-embedding-images-0.6b.tar"
    $embeddingArchive = Join-Path $destinationPath "lig-qwen3-embedding-images-0.6b.tar.gz"
    Invoke-Docker (@("save", "--output", $embeddingTar) + $embeddingImages)
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
}

$paddleOcrVlImages = @()
$paddleOcrVlImageIds = [ordered]@{}
if ($IncludePaddleOcrVl) {
    $configuration = @{}
    foreach ($line in Get-Content -LiteralPath (Join-Path $deploymentDirectory ".env.lig") -Encoding UTF8) {
        if ($line -match '^\s*([^#=]+?)\s*=\s*(.*)\s*$') { $configuration[$matches[1].Trim()] = $matches[2].Trim() }
    }
    $paddleOcrVlImages = @(
        $configuration["PADDLEOCR_VL_API_IMAGE"],
        $configuration["PADDLEOCR_VL_VLM_IMAGE"],
        $configuration["PADDLEOCR_VL_GATEWAY_IMAGE"]
    )
    foreach ($image in $paddleOcrVlImages) {
        if ([string]::IsNullOrWhiteSpace($image)) { throw "PaddleOCR-VL 이미지 설정이 비어 있습니다." }
        $inspect = Invoke-DockerCapture -Arguments @("image", "inspect", "--format", "{{.Id}}", $image) -AllowFailure
        if ($inspect.ExitCode -ne 0) { throw "선택한 PaddleOCR-VL 이미지가 없습니다: $image" }
        $paddleOcrVlImageIds[$image] = ([string]($inspect.Lines | Where-Object { $_ -match '^sha256:[0-9a-fA-F]{64}$' } | Select-Object -Last 1)).Trim()
        if (-not $paddleOcrVlImageIds[$image]) { throw "PaddleOCR-VL 이미지 ID를 확인하지 못했습니다: $image" }
    }
    $vlTar = Join-Path $destinationPath "lig-paddleocr-vl-1.6-images.tar"
    $vlArchive = Join-Path $destinationPath "lig-paddleocr-vl-1.6-images.tar.gz"
    Invoke-Docker (@("save", "--output", $vlTar) + $paddleOcrVlImages)
    Write-Host "선택 PaddleOCR-VL-1.6 이미지 압축파일을 생성합니다."
    $vlInput = $null
    $vlOutput = $null
    $vlGzip = $null
    try {
        $vlInput = [IO.File]::OpenRead($vlTar)
        $vlOutput = [IO.File]::Create($vlArchive)
        $vlGzip = [IO.Compression.GZipStream]::new($vlOutput, [IO.Compression.CompressionLevel]::Optimal, $false)
        $vlInput.CopyTo($vlGzip, 1MB)
    }
    finally {
        if ($null -ne $vlGzip) { $vlGzip.Dispose() }
        if ($null -ne $vlOutput) { $vlOutput.Dispose() }
        if ($null -ne $vlInput) { $vlInput.Dispose() }
        if (Test-Path -LiteralPath $vlTar) { Remove-Item -LiteralPath $vlTar -Force }
    }
}

$destinationPrefix = $destinationPath.TrimEnd('\') + '\'
$records = Get-ChildItem -LiteralPath $destinationPath -File -Recurse | Where-Object {
    $_.Name -ne "manifest.json"
} | Sort-Object FullName | ForEach-Object {
    $relativePath = $_.FullName.Substring($destinationPrefix.Length).Replace('\', '/')
    [pscustomobject]@{ file = $relativePath; bytes = $_.Length; sha256 = Get-Sha256Hex $_.FullName }
}
$manifest = [pscustomobject]@{
    bundleFormat = 9
    ragflowVersion = "v0.26.4"
    uiImage = "lig/ragflow-ui:v0.26.4-3"
    gpuIncluded = [bool]$IncludeGpu
    gpuUiImage = if ($IncludeGpu) { "lig/ragflow-ui-gpu:v0.26.4-3" } else { $null }
    mcpImage = "lig/ragflow-mcp:v0.26.4-3"
    ocrImage = "lig/paddleocr-ko:v0.26.4-3"
    gpuOcrImage = if ($IncludeGpu) { "lig/paddleocr-ko-gpu:v0.26.4-3" } else { $null }
    images = @($images)
    imageIds = $imageIds
    embeddingImages = @($embeddingImages)
    embeddingImageIds = $embeddingImageIds
    embeddingIncluded = [bool]$IncludeEmbedding
    embeddingModel = if ($IncludeEmbedding) { "Qwen/Qwen3-Embedding-0.6B" } else { $null }
    embeddingModelRevision = if ($IncludeEmbedding) { "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3" } else { $null }
    embeddingRuntime = if ($IncludeEmbedding) { "TEI cpu-1.9" } else { $null }
    paddleOcrVlIncluded = [bool]$IncludePaddleOcrVl
    paddleOcrVlModel = if ($IncludePaddleOcrVl) { "PaddleOCR-VL-1.6" } else { $null }
    paddleOcrVlImages = @($paddleOcrVlImages)
    paddleOcrVlImageIds = $paddleOcrVlImageIds
    createdAt = (Get-Date).ToString("o")
    files = @($records)
}
$manifestPath = Join-Path $destinationPath "manifest.json"
$manifestJson = $manifest | ConvertTo-Json -Depth 5
[IO.File]::WriteAllText($manifestPath, $manifestJson, [Text.UTF8Encoding]::new($false))
$manifest | ConvertTo-Json -Depth 5
