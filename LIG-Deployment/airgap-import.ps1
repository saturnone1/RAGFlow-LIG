param(
    [Parameter(Mandatory)]
    [string]$Source
)

$ErrorActionPreference = "Stop"
$sourcePath = [IO.Path]::GetFullPath($Source)
if (-not (Test-Path -LiteralPath $sourcePath -PathType Container)) { throw "Source directory not found: $sourcePath" }
$imageArchive = Join-Path $sourcePath "lig-ragflow-images-v0.26.4.tar.gz"
$manifestPath = Join-Path $sourcePath "manifest.json"
foreach ($file in @($imageArchive, $manifestPath)) { if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Required archive not found: $file" } }

$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.bundleFormat -ne 2) {
    throw "Unsupported air-gap bundle format: $($manifest.bundleFormat)"
}
if ($manifest.uiImage -ne "lig/ragflow-ui:v0.26.4-1") {
    throw "Unsupported or missing UI image in manifest: $($manifest.uiImage)"
}
$includesOllama = [bool]$manifest.includesOllama
$modelArchive = Join-Path $sourcePath "lig-ollama-models.tgz"
if ($includesOllama -and -not (Test-Path -LiteralPath $modelArchive -PathType Leaf)) {
    throw "Required Ollama model archive not found: $modelArchive"
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

$secretFile = Join-Path $PSScriptRoot ".env.secret"
if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot ".env.secret.example") -Destination $secretFile
    Write-Warning "Created LIG-Deployment\.env.secret from the example. Replace its placeholder API key after creating a RAGFlow API key."
}
$logDirectory = Join-Path $PSScriptRoot "ragflow-logs"
if (-not (Test-Path -LiteralPath $logDirectory -PathType Container)) {
    New-Item -ItemType Directory -Path $logDirectory | Out-Null
}

$previousProfiles = $env:COMPOSE_PROFILES
try {
    $env:COMPOSE_PROFILES = if ($includesOllama) { "infinity,cpu,ollama" } else { "infinity,cpu" }
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
}

if ($includesOllama) {
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
    docker exec $container ollama show $manifest.ollamaModel
    if ($LASTEXITCODE -ne 0) { throw "Restored embedding model validation failed" }
}
