param(
    [Parameter(Mandatory)]
    [string]$Source,

    [ValidateSet("cpu", "gpu")]
    [string]$Device = "cpu"
)

$ErrorActionPreference = "Stop"
$sourcePath = [IO.Path]::GetFullPath($Source)
if (-not (Test-Path -LiteralPath $sourcePath -PathType Container)) { throw "Source directory not found: $sourcePath" }
$imageArchive = Join-Path $sourcePath "lig-ragflow-images-v0.26.4.tar.gz"
$manifestPath = Join-Path $sourcePath "manifest.json"
foreach ($file in @($imageArchive, $manifestPath)) { if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Required archive not found: $file" } }

$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.bundleFormat -ne 7) {
    throw "Unsupported air-gap bundle format: $($manifest.bundleFormat)"
}
if ($manifest.uiImage -ne "lig/ragflow-ui:v0.26.4-1") {
    throw "Unsupported or missing UI image in manifest: $($manifest.uiImage)"
}
if ($manifest.gpuUiImage -ne "lig/ragflow-ui-gpu:v0.26.4-1") {
    throw "Unsupported or missing GPU UI image in manifest: $($manifest.gpuUiImage)"
}
if ($manifest.mcpImage -ne "lig/ragflow-mcp:v0.26.4-1") {
    throw "Unsupported or missing management MCP image in manifest: $($manifest.mcpImage)"
}
if ($manifest.ocrImage -ne "lig/paddleocr-ko:v0.26.4-1") {
    throw "Unsupported or missing Korean OCR image in manifest: $($manifest.ocrImage)"
}
if ($manifest.gpuOcrImage -ne "lig/paddleocr-ko-gpu:v0.26.4-1") {
    throw "Unsupported or missing GPU Korean OCR image in manifest: $($manifest.gpuOcrImage)"
}
foreach ($requiredImage in @($manifest.uiImage, $manifest.gpuUiImage, $manifest.mcpImage, $manifest.ocrImage, $manifest.gpuOcrImage)) {
    if ($requiredImage -notin @($manifest.images)) { throw "Required image is absent from manifest images: $requiredImage" }
}
if ($manifest.embeddingModel -ne "Qwen/Qwen3-Embedding-0.6B") {
    throw "Unsupported or missing optional embedding model in manifest: $($manifest.embeddingModel)"
}
$expectedEmbeddingImages = @("lig/qwen3-embedding-tei:0.6b-1", "lig/qwen3-embedding-adapter:0.6b-1")
if ((@($manifest.embeddingImages | Sort-Object) -join "`n") -ne (@($expectedEmbeddingImages | Sort-Object) -join "`n")) {
    throw "Optional embedding image list is missing or unsupported."
}
foreach ($record in $manifest.files) {
    $file = [IO.Path]::GetFullPath((Join-Path $sourcePath ([string]$record.file)))
    $sourcePrefix = $sourcePath.TrimEnd('\') + '\'
    if (-not $file.StartsWith($sourcePrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Manifest contains an invalid path: $($record.file)"
    }
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Manifest file not found: $file" }
    if ((Get-Item -LiteralPath $file).Length -ne [long]$record.bytes) { throw "File size mismatch: $($record.file)" }
    $actual = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne ([string]$record.sha256).ToLowerInvariant()) { throw "SHA-256 mismatch: $($record.file)" }
}
Write-Host "Air-gap archive SHA-256 validation passed."

& docker version *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker Engine is not available. Start Docker Desktop and try again." }
& docker compose version *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker Compose v2 is not available." }

docker load --input $imageArchive
if ($LASTEXITCODE -ne 0) { throw "docker load failed" }
docker image inspect $manifest.uiImage *> $null
if ($LASTEXITCODE -ne 0) { throw "Custom UI image was not loaded: $($manifest.uiImage)" }
docker image inspect $manifest.gpuUiImage *> $null
if ($LASTEXITCODE -ne 0) { throw "GPU UI image was not loaded: $($manifest.gpuUiImage)" }
docker image inspect $manifest.mcpImage *> $null
if ($LASTEXITCODE -ne 0) { throw "Management MCP image was not loaded: $($manifest.mcpImage)" }
docker image inspect $manifest.ocrImage *> $null
if ($LASTEXITCODE -ne 0) { throw "Korean PaddleOCR image was not loaded: $($manifest.ocrImage)" }
docker image inspect $manifest.gpuOcrImage *> $null
if ($LASTEXITCODE -ne 0) { throw "GPU Korean PaddleOCR image was not loaded: $($manifest.gpuOcrImage)" }
if (-not $manifest.imageIds) { throw "Manifest image IDs are missing." }
foreach ($image in @($manifest.images)) {
    $expectedIdProperty = $manifest.imageIds.PSObject.Properties[[string]$image]
    if (-not $expectedIdProperty) { throw "Manifest image ID is missing: $image" }
    $actualId = (& docker image inspect --format '{{.Id}}' $image).Trim()
    if ($LASTEXITCODE -ne 0 -or $actualId -ne [string]$expectedIdProperty.Value) {
        throw "Loaded image ID does not match the manifest: $image"
    }
}

if ($Device -eq "gpu") {
    Write-Host "Validating NVIDIA GPU access from the RAGFlow image..."
    docker run --rm --gpus all --entrypoint nvidia-smi $manifest.gpuUiImage --query-gpu=name,memory.total,driver_version --format=csv,noheader
    if ($LASTEXITCODE -ne 0) {
        throw "NVIDIA GPU validation failed. Install a supported NVIDIA driver and NVIDIA Container Toolkit, enable GPU access in Docker Desktop, and retry."
    }
    docker run --rm --gpus all --entrypoint /ragflow/.venv/bin/python $manifest.gpuUiImage -c "import ctypes; ctypes.CDLL('libcublasLt.so.12'); import onnxruntime as ort; session=ort.InferenceSession('/ragflow/rag/res/deepdoc/layout.onnx', providers=['CUDAExecutionProvider']); providers=session.get_providers(); assert providers and providers[0] == 'CUDAExecutionProvider', f'DeepDoc CUDA provider unavailable: {providers}'; print('DeepDoc ONNX provider:', providers[0])"
    if ($LASTEXITCODE -ne 0) {
        throw "The GPU is visible, but DeepDoc could not create a CUDA ONNX session. Check the NVIDIA driver and CUDA 12/cuDNN 9 compatibility."
    }
    docker run --rm --gpus all --entrypoint /ragflow/.venv/bin/python $manifest.gpuOcrImage -c "from pathlib import Path; import ctypes, rapidocr; ctypes.CDLL('libcublasLt.so.12'); import onnxruntime as ort; assert Path('/dev/nvidiactl').exists(), 'NVIDIA device is unavailable'; model=Path(rapidocr.__file__).resolve().parent/'models'/'korean_PP-OCRv5_rec_mobile.onnx'; session=ort.InferenceSession(str(model), providers=['CUDAExecutionProvider']); providers=session.get_providers(); assert providers and providers[0] == 'CUDAExecutionProvider', f'PaddleOCR CUDA provider unavailable: {providers}'; print('PaddleOCR ONNX provider:', providers[0])"
    if ($LASTEXITCODE -ne 0) {
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
$previousWorkers = $env:TASK_EXECUTOR_WORKERS
try {
    $env:DEVICE = $Device
    $env:COMPOSE_PROFILES = "infinity,$Device"
    if ($Device -eq "gpu") {
        $env:TASK_EXECUTOR_WORKERS = "1"
    }
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
    if ($null -eq $previousWorkers) { Remove-Item Env:TASK_EXECUTOR_WORKERS -ErrorAction SilentlyContinue } else { $env:TASK_EXECUTOR_WORKERS = $previousWorkers }
}
