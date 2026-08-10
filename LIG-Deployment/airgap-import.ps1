param(
    [Parameter(Mandatory)]
    [string]$Source,

    [ValidateSet("cpu", "gpu")]
    [string]$Device = "cpu"
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
$sourcePath = [IO.Path]::GetFullPath($Source)
if (-not (Test-Path -LiteralPath $sourcePath -PathType Container)) { throw "Source directory not found: $sourcePath" }
$imageArchive = Join-Path $sourcePath "lig-ragflow-images-v0.26.4.tar.gz"
$manifestPath = Join-Path $sourcePath "manifest.json"
foreach ($file in @($imageArchive, $manifestPath)) { if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Required archive not found: $file" } }

$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.bundleFormat -ne 9) {
    throw "Unsupported air-gap bundle format: $($manifest.bundleFormat)"
}
if ($manifest.uiImage -ne "lig/ragflow-ui:v0.26.4-3") {
    throw "Unsupported or missing UI image in manifest: $($manifest.uiImage)"
}
if ($manifest.mcpImage -ne "lig/ragflow-mcp:v0.26.4-3") {
    throw "Unsupported or missing management MCP image in manifest: $($manifest.mcpImage)"
}
if ($manifest.ocrImage -ne "lig/paddleocr-ko:v0.26.4-3") {
    throw "Unsupported or missing Korean OCR image in manifest: $($manifest.ocrImage)"
}
foreach ($requiredImage in @($manifest.uiImage, $manifest.mcpImage, $manifest.ocrImage)) {
    if ($requiredImage -notin @($manifest.images)) { throw "Required image is absent from manifest images: $requiredImage" }
}
if ($Device -eq "gpu") {
    if (-not $manifest.gpuIncluded) { throw "This bundle does not include GPU images. Export it again with -IncludeGpu." }
    if ($manifest.gpuUiImage -ne "lig/ragflow-ui-gpu:v0.26.4-3") { throw "Unsupported GPU UI image: $($manifest.gpuUiImage)" }
    if ($manifest.gpuOcrImage -ne "lig/paddleocr-ko-gpu:v0.26.4-3") { throw "Unsupported GPU OCR image: $($manifest.gpuOcrImage)" }
    foreach ($requiredImage in @($manifest.gpuUiImage, $manifest.gpuOcrImage)) {
        if ($requiredImage -notin @($manifest.images)) { throw "Required GPU image is absent from manifest images: $requiredImage" }
    }
}
foreach ($record in $manifest.files) {
    $file = [IO.Path]::GetFullPath((Join-Path $sourcePath ([string]$record.file)))
    $sourcePrefix = $sourcePath.TrimEnd('\') + '\'
    if (-not $file.StartsWith($sourcePrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Manifest contains an invalid path: $($record.file)"
    }
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Manifest file not found: $file" }
    if ((Get-Item -LiteralPath $file).Length -ne [long]$record.bytes) { throw "File size mismatch: $($record.file)" }
    $actual = Get-Sha256Hex $file
    if ($actual -ne ([string]$record.sha256).ToLowerInvariant()) { throw "SHA-256 mismatch: $($record.file)" }
}
Write-Host "Air-gap archive SHA-256 validation passed."

$dockerVersion = Invoke-DockerCapture -Arguments @("version", "--format", "{{.Server.Version}}") -AllowFailure
if ($dockerVersion.ExitCode -ne 0) { throw "Docker Engine is not available. Start Docker Desktop and try again." }
$composeVersion = Invoke-DockerCapture -Arguments @("compose", "version", "--short") -AllowFailure
if ($composeVersion.ExitCode -ne 0) { throw "Docker Compose v2 is not available." }

Invoke-Docker @("load", "--input", $imageArchive)
foreach ($loadedImage in @($manifest.uiImage, $manifest.mcpImage, $manifest.ocrImage)) {
    $inspect = Invoke-DockerCapture -Arguments @("image", "inspect", "--format", "{{.Id}}", $loadedImage) -AllowFailure
    if ($inspect.ExitCode -ne 0) { throw "Required image was not loaded: $loadedImage" }
}
if ($manifest.gpuIncluded) {
    foreach ($loadedImage in @($manifest.gpuUiImage, $manifest.gpuOcrImage)) {
        $inspect = Invoke-DockerCapture -Arguments @("image", "inspect", "--format", "{{.Id}}", $loadedImage) -AllowFailure
        if ($inspect.ExitCode -ne 0) { throw "Required GPU image was not loaded: $loadedImage" }
    }
}
if (-not $manifest.imageIds) { throw "Manifest image IDs are missing." }
foreach ($image in @($manifest.images)) {
    $expectedIdProperty = $manifest.imageIds.PSObject.Properties[[string]$image]
    if (-not $expectedIdProperty) { throw "Manifest image ID is missing: $image" }
    $inspect = Invoke-DockerCapture -Arguments @("image", "inspect", "--format", "{{.Id}}", $image) -AllowFailure
    $actualId = ([string]($inspect.Lines | Where-Object { $_ -match '^sha256:[0-9a-fA-F]{64}$' } | Select-Object -Last 1)).Trim()
    if ($inspect.ExitCode -ne 0 -or $actualId -ne [string]$expectedIdProperty.Value) {
        throw "Loaded image ID does not match the manifest: $image"
    }
}

$verificationScript = Join-Path $PSScriptRoot "verify-cpu-images.ps1"
if (-not (Test-Path -LiteralPath $verificationScript -PathType Leaf)) {
    $verificationScript = Join-Path (Split-Path $PSScriptRoot -Parent) "verify-cpu-images.ps1"
}
if (-not (Test-Path -LiteralPath $verificationScript -PathType Leaf)) {
    throw "CPU image verification script is missing from the bundle."
}
& $verificationScript `
    -RagFlowImage $manifest.uiImage `
    -PaddleOcrImage $manifest.ocrImage `
    -McpImage $manifest.mcpImage

if ($Device -eq "gpu") {
    Write-Host "Validating NVIDIA GPU access from the RAGFlow image..."
    try {
        Invoke-Docker @("run", "--rm", "--gpus", "all", "--entrypoint", "nvidia-smi", $manifest.gpuUiImage, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader")
    } catch {
        throw "NVIDIA GPU validation failed. Install a supported NVIDIA driver and NVIDIA Container Toolkit, enable GPU access in Docker Desktop, and retry."
    }
    try {
        Invoke-Docker @("run", "--rm", "--gpus", "all", "--entrypoint", "/ragflow/.venv/bin/python", $manifest.gpuUiImage, "-c", "import ctypes; ctypes.CDLL('libcublasLt.so.12'); import onnxruntime as ort; session=ort.InferenceSession('/ragflow/rag/res/deepdoc/layout.onnx', providers=['CUDAExecutionProvider']); providers=session.get_providers(); assert providers and providers[0] == 'CUDAExecutionProvider', f'DeepDoc CUDA provider unavailable: {providers}'; print('DeepDoc ONNX provider:', providers[0])")
    } catch {
        throw "The GPU is visible, but DeepDoc could not create a CUDA ONNX session. Check the NVIDIA driver and CUDA 12/cuDNN 9 compatibility."
    }
    try {
        Invoke-Docker @("run", "--rm", "--gpus", "all", "--entrypoint", "/ragflow/.venv/bin/python", $manifest.gpuOcrImage, "-c", "from pathlib import Path; import ctypes, rapidocr; ctypes.CDLL('libcublasLt.so.12'); import onnxruntime as ort; model=Path(rapidocr.__file__).resolve().parent/'models'/'korean_PP-OCRv5_rec_mobile.onnx'; session=ort.InferenceSession(str(model), providers=['CUDAExecutionProvider']); providers=session.get_providers(); assert providers and providers[0] == 'CUDAExecutionProvider', f'PaddleOCR CUDA provider unavailable: {providers}'; print('PaddleOCR ONNX provider:', providers[0])")
    } catch {
        throw "The GPU is visible, but the PaddleOCR image cannot use CUDAExecutionProvider. Check the NVIDIA driver and CUDA 12/cuDNN 9 compatibility."
    }
}

$secretFile = Join-Path $PSScriptRoot ".env.secret"
if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot ".env.secret.example") -Destination $secretFile
    Write-Warning "Created LIG-Deployment\.env.secret from the example. Replace its placeholder API key after creating a RAGFlow API key."
}
$logDirectory = Join-Path $PSScriptRoot "ragflow-logs"
if (-not (Test-Path -LiteralPath $logDirectory -PathType Container)) {
    New-Item -ItemType Directory -Path $logDirectory | Out-Null
}
$mcpDataDirectory = Join-Path $PSScriptRoot "mcp-files"
if (-not (Test-Path -LiteralPath $mcpDataDirectory -PathType Container)) {
    New-Item -ItemType Directory -Path $mcpDataDirectory | Out-Null
}

$previousProfiles = $env:COMPOSE_PROFILES
$previousDevice = $env:DEVICE
try {
    $env:DEVICE = $Device
    $env:COMPOSE_PROFILES = "infinity,$Device"
    & (Join-Path $PSScriptRoot "lig-ragflow.ps1") start
    if ($LASTEXITCODE -ne 0) { throw "RAGFlow start failed" }
}
finally {
    if ($null -eq $previousProfiles) {
        Remove-Item Env:COMPOSE_PROFILES -ErrorAction SilentlyContinue
    }
    else {
        $env:COMPOSE_PROFILES = $previousProfiles
    }
    if ($null -eq $previousDevice) { Remove-Item Env:DEVICE -ErrorAction SilentlyContinue } else { $env:DEVICE = $previousDevice }
}
