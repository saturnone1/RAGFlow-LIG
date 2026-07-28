param(
    [ValidateSet("config", "pull", "build", "gpu-build", "ui-build", "mcp-build", "ocr-build", "embedding-build", "embedding-start", "embedding-stop", "embedding-status", "embedding-test", "start", "stop", "status", "diagnostics", "logs")]
    [string]$Action = "status"
)

$ErrorActionPreference = "Stop"
$deploymentDirectory = $PSScriptRoot
$workspaceDirectory = Split-Path $deploymentDirectory -Parent
$dockerDirectory = Join-Path $workspaceDirectory "RAGFlow\docker"
$upstreamEnvFile = Join-Path $dockerDirectory ".env"
$ligEnvFile = Join-Path $deploymentDirectory ".env.lig"
$secretFile = Join-Path $deploymentDirectory ".env.secret"
$logDirectory = Join-Path $deploymentDirectory "ragflow-logs"
$mcpDataDirectory = Join-Path $deploymentDirectory "mcp-files"
$uiDockerfile = Join-Path $workspaceDirectory "LIG-UI\Dockerfile"
$gpuUiDockerfile = Join-Path $workspaceDirectory "LIG-UI\Dockerfile.gpu"
$mcpDirectory = Join-Path $workspaceDirectory "RAGFlow-MCP-LIG"
$mcpDockerfile = Join-Path $mcpDirectory "Dockerfile"
$ocrDirectory = Join-Path $workspaceDirectory "LIG-PaddleOCR"
$ocrDockerfile = Join-Path $ocrDirectory "Dockerfile"
$embeddingDirectory = Join-Path $workspaceDirectory "LIG-Embedding"
$embeddingModelDockerfile = Join-Path $embeddingDirectory "Dockerfile.model"
$embeddingAdapterDockerfile = Join-Path $embeddingDirectory "Dockerfile.adapter"

$env:RAGFLOW_UPSTREAM_ENV_FILE = $upstreamEnvFile
$env:LIG_ENV_FILE = $ligEnvFile
$env:LIG_LOG_DIRECTORY = $logDirectory
$env:LIG_MCP_DATA_DIRECTORY = $mcpDataDirectory

foreach ($runtimeDirectory in @($logDirectory, $mcpDataDirectory)) {
    if (-not (Test-Path -LiteralPath $runtimeDirectory -PathType Container)) {
        New-Item -ItemType Directory -Path $runtimeDirectory | Out-Null
    }
}

$composeArguments = @(
    "compose",
    "--project-name", "lig-ragflow",
    "--project-directory", $dockerDirectory,
    "--env-file", (Join-Path $dockerDirectory ".env"),
    "--env-file", $ligEnvFile
)
$composeArguments += @("--env-file", $secretFile)
$composeArguments += @(
    "-f", (Join-Path $dockerDirectory "docker-compose.yml"),
    "-f", (Join-Path $deploymentDirectory "docker-compose.lig.yml")
)

function Invoke-Compose([string[]]$Arguments) {
    $dockerExecutable = (Get-Command docker -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    $previousErrorActionPreference = $ErrorActionPreference
    $dockerExitCode = 1
    try {
        # Windows PowerShell 5.1 turns redirected native stderr into
        # NativeCommandError records. Compose writes progress to stderr even
        # when it succeeds, so keep the text visible and trust its exit code.
        $ErrorActionPreference = "Continue"
        & $dockerExecutable @composeArguments @Arguments 2>&1 | ForEach-Object { Write-Host $_ }
        $dockerExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($dockerExitCode -ne 0) {
        throw "docker compose failed with exit code $dockerExitCode"
    }
}

function Assert-FreeSpace {
    $drive = Get-PSDrive -Name C
    $freeGiB = [math]::Round($drive.Free / 1GB, 1)
    if ($freeGiB -lt 20) {
        throw "C drive free space is ${freeGiB} GiB. At least 20 GiB is required before pulling or starting RAGFlow."
    }
    Write-Host "C drive free: ${freeGiB} GiB"
}

function Get-EnvFileValues([string]$Path) {
    $values = @{}
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $values }
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
        $name, $value = $line -split '=', 2
        $values[$name.Trim()] = $value.Trim()
    }
    return $values
}

function Get-ConfigurationValue([hashtable]$Configuration, [string]$Name, [string]$Default = $null) {
    $environmentValue = [Environment]::GetEnvironmentVariable($Name)
    if ($null -ne $environmentValue -and $environmentValue -ne "") { return $environmentValue }
    if ($Configuration.ContainsKey($Name)) { return $Configuration[$Name] }
    return $Default
}

function New-DocumentPasswordKey {
    $bytes = New-Object byte[] 32
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) }
    finally { $generator.Dispose() }
    return [Convert]::ToBase64String($bytes)
}

function Ensure-DocumentPasswordKey {
    if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) {
        Copy-Item -LiteralPath (Join-Path $deploymentDirectory ".env.secret.example") -Destination $secretFile
    }
    $lines = @(Get-Content -LiteralPath $secretFile)
    $keyLineIndex = -1
    $legacyKeyLineIndex = -1
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match '^\s*LIG_DOCUMENT_PASSWORD_KEY=') { $keyLineIndex = $index }
        if ($lines[$index] -match '^\s*LIG_PDF_PASSWORD_KEY=') { $legacyKeyLineIndex = $index }
    }
    $currentValue = if ($keyLineIndex -ge 0) { ($lines[$keyLineIndex] -split '=', 2)[1].Trim() } else { "" }
    if (([string]::IsNullOrWhiteSpace($currentValue) -or $currentValue -eq "generate-a-base64-encoded-32-byte-key") -and $legacyKeyLineIndex -ge 0) {
        $legacyValue = ($lines[$legacyKeyLineIndex] -split '=', 2)[1].Trim()
        if (-not [string]::IsNullOrWhiteSpace($legacyValue) -and $legacyValue -ne "generate-a-base64-encoded-32-byte-key") {
            if ($keyLineIndex -ge 0) { $lines[$keyLineIndex] = "LIG_DOCUMENT_PASSWORD_KEY=$legacyValue" }
            else { $lines[$legacyKeyLineIndex] = "LIG_DOCUMENT_PASSWORD_KEY=$legacyValue"; $keyLineIndex = $legacyKeyLineIndex; $legacyKeyLineIndex = -1 }
            $currentValue = $legacyValue
            Write-Host "Migrated the existing document password encryption key name."
        }
    }
    if ([string]::IsNullOrWhiteSpace($currentValue) -or $currentValue -eq "generate-a-base64-encoded-32-byte-key") {
        $keyLine = "LIG_DOCUMENT_PASSWORD_KEY=$(New-DocumentPasswordKey)"
        if ($keyLineIndex -ge 0) { $lines[$keyLineIndex] = $keyLine } else { $lines += $keyLine }
        Write-Host "Generated the local document password encryption key in LIG-Deployment\.env.secret."
    }
    if ($legacyKeyLineIndex -ge 0) { $lines = @($lines | Where-Object { $_ -notmatch '^\s*LIG_PDF_PASSWORD_KEY=' }) }
    if (-not ($lines | Where-Object { $_ -match '^\s*LIG_DOCUMENT_PASSWORD_KEY_ID=' })) {
        $lines += "LIG_DOCUMENT_PASSWORD_KEY_ID=primary"
    }
    if (-not ($lines | Where-Object { $_ -match '^\s*LIG_DOCUMENT_PASSWORD_PREVIOUS_KEYS=' })) {
        $lines += "LIG_DOCUMENT_PASSWORD_PREVIOUS_KEYS="
    }
    [IO.File]::WriteAllLines($secretFile, $lines, [Text.UTF8Encoding]::new($false))
}

function Assert-LigConfiguration {
    Ensure-DocumentPasswordKey
    $configuration = Get-EnvFileValues $ligEnvFile
    $workerValue = Get-ConfigurationValue $configuration "TASK_EXECUTOR_WORKERS" "1"
    $workers = 0
    if (-not [int]::TryParse($workerValue, [ref]$workers) -or $workers -lt 1) {
        throw "TASK_EXECUTOR_WORKERS must be a positive integer. Current value: $workerValue"
    }
    foreach ($settingName in @("DOC_BULK_SIZE", "EMBEDDING_BATCH_SIZE", "THREAD_POOL_MAX_WORKERS")) {
        $settingValue = Get-ConfigurationValue $configuration $settingName
        if ([string]::IsNullOrWhiteSpace($settingValue)) { continue }
        $parsed = 0
        if (-not [int]::TryParse($settingValue, [ref]$parsed) -or $parsed -lt 1) {
            throw "$settingName must be a positive integer. Current value: $settingValue"
        }
    }
}

function Protect-DiagnosticText([string]$Text) {
    if (-not $Text) { return $Text }
    $protected = $Text -replace 'nvapi-[A-Za-z0-9_-]+', '<redacted-nvidia-key>'
    $protected = $protected -replace '(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+', '${1}<redacted>'
    $protected = $protected -replace '(?i)(api[_-]?key\s*["''=:]+\s*)[^\s,"'']+', '${1}<redacted>'
    return $protected
}

function Invoke-Diagnostics {
    $configuration = Get-EnvFileValues $ligEnvFile
    $secrets = Get-EnvFileValues $secretFile
    $apiKey = $secrets["RAGFLOW_MCP_API_KEY"]
    $apiBinding = Get-ConfigurationValue $configuration "SVR_HTTP_PORT" "127.0.0.1:42301"
    $apiPort = ($apiBinding -split ':')[-1]
    if ($apiPort -notmatch '^\d+$') {
        throw "SVR_HTTP_PORT must end with a numeric port. Current value: $apiBinding"
    }
    $apiBase = "http://127.0.0.1:$apiPort"
    $serviceHealth = $null
    $apiError = $null
    $dockerServerVersion = (& docker version --format '{{.Server.Version}}' 2>$null)
    $dockerError = if ($LASTEXITCODE -eq 0) { $null } else { "Docker engine is unavailable." }

    try {
        $headers = @{}
        if ($apiKey -and $apiKey -notmatch '^replace-') { $headers["Authorization"] = "Bearer $apiKey" }
        $response = Invoke-RestMethod -Uri "$apiBase/api/v1/system/status" -Headers $headers -TimeoutSec 10
        $serviceHealth = $response.data
    } catch {
        $apiError = $_.Exception.Message
    }

    $composeRows = @(& docker @composeArguments ps --format json 2>$null | ForEach-Object {
        try { $_ | ConvertFrom-Json } catch { $null }
    } | Where-Object { $null -ne $_ })

    $containerNames = @($composeRows | ForEach-Object { $_.Name } | Where-Object { $_ })
    $stats = @()
    if ($containerNames.Count -gt 0) {
        $stats = @(& docker stats --no-stream --format '{{json .}}' @containerNames 2>$null | ForEach-Object {
            try { $_ | ConvertFrom-Json } catch { $null }
        } | Where-Object { $null -ne $_ })
    }

    $timingSamples = @()
    $recentErrors = @()
    $ragflowContainer = $containerNames | Where-Object { $_ -match 'ragflow-(cpu|gpu)' } | Select-Object -First 1
    $ragflowHostname = $null
    if ($ragflowContainer) {
        $ragflowHostname = (& docker inspect --format '{{.Config.Hostname}}' $ragflowContainer 2>$null)
        $logLines = @(& docker logs --tail 2000 $ragflowContainer 2>&1)
        $timingSamples = @($logLines | Where-Object {
            $_ -match '(Chunk doc|Indexing doc|\[Done\]).*elapsed\s*:\s*[0-9]'
        } | Select-Object -Last 20 | ForEach-Object { Protect-DiagnosticText $_ })
        $recentErrors = @($logLines | Where-Object {
            $_ -match '(?i)(\[ERROR\]|Traceback|exception:)'
        } | Select-Object -Last 20 | ForEach-Object { Protect-DiagnosticText $_ })
    }

    $heartbeats = @()
    if ($serviceHealth -and $serviceHealth.task_executor_heartbeats) {
        $heartbeats = @($serviceHealth.task_executor_heartbeats.PSObject.Properties | ForEach-Object {
            [pscustomobject]@{
                Worker = $_.Name
                CurrentContainer = [bool]($ragflowHostname -and $_.Name -match [regex]::Escape($ragflowHostname))
                SamplesInLast30Minutes = @($_.Value).Count
            }
        })
    }

    $report = [pscustomobject]@{
        GeneratedAt = (Get-Date).ToString("o")
        DockerServerVersion = $dockerServerVersion
        DockerError = $dockerError
        Configuration = [pscustomobject]@{
            Device = Get-ConfigurationValue $configuration "DEVICE"
            DocumentEngine = Get-ConfigurationValue $configuration "DOC_ENGINE"
            Profiles = Get-ConfigurationValue $configuration "COMPOSE_PROFILES"
            TaskExecutorWorkers = Get-ConfigurationValue $configuration "TASK_EXECUTOR_WORKERS" "1"
            DocumentBulkSize = Get-ConfigurationValue $configuration "DOC_BULK_SIZE"
            EmbeddingBatchSize = Get-ConfigurationValue $configuration "EMBEDDING_BATCH_SIZE"
            ThreadPoolWorkers = Get-ConfigurationValue $configuration "THREAD_POOL_MAX_WORKERS"
            DoclingEnabled = Get-ConfigurationValue $configuration "USE_DOCLING"
            EmbeddingMode = if ($containerNames -contains "lig-ragflow-qwen3-embedding-1") { "optional Qwen3 TEI CPU service" } else { "configured in RAGFlow (external provider)" }
            KoreanOcr = "PP-OCRv5 (CPU/GPU follows DEVICE)"
            StandaloneDeepDocEnabled = ((Get-ConfigurationValue $configuration "COMPOSE_PROFILES") -split ',' -contains 'deepdoc')
        }
        Services = $composeRows | Select-Object Name, Service, State, Health, Status, Ports
        Health = if ($serviceHealth) { [pscustomobject]@{
            DocumentEngine = $serviceHealth.doc_engine
            Storage = $serviceHealth.storage
            Database = $serviceHealth.database
            Redis = $serviceHealth.redis
        }} else { $null }
        TaskExecutorHeartbeats = $heartbeats
        CurrentTaskExecutorHeartbeatCount = @($heartbeats | Where-Object { $_.CurrentContainer }).Count
        ContainerStats = $stats | Select-Object Name, CPUPerc, MemUsage, MemPerc, BlockIO, NetIO
        RecentStageTimings = $timingSamples
        RecentErrors = $recentErrors
        ApiError = $apiError
    }

    $report | ConvertTo-Json -Depth 8
}

switch ($Action) {
    "config" {
        Assert-LigConfiguration
        Invoke-Compose @("config", "--quiet")
        Write-Host "RAGFlow Compose configuration is valid."
    }
    "pull" {
        Assert-FreeSpace
        & docker pull "infiniflow/ragflow:v0.26.4"
        if ($LASTEXITCODE -ne 0) { throw "Official RAGFlow image pull failed" }
        Invoke-Compose @("pull", "infinity", "mysql", "minio", "redis")
    }
    "ui-build" {
        Assert-FreeSpace
        & docker build --file $uiDockerfile --tag "lig/ragflow-ui:v0.26.4-1" $workspaceDirectory
        if ($LASTEXITCODE -ne 0) {
            throw "LIG UI Docker build failed with exit code $LASTEXITCODE"
        }
        Write-Host "Built lig/ragflow-ui:v0.26.4-1"
    }
    "mcp-build" {
        Assert-FreeSpace
        & docker build --file $mcpDockerfile --tag "lig/ragflow-mcp:v0.26.4-1" $mcpDirectory
        if ($LASTEXITCODE -ne 0) {
            throw "LIG management MCP Docker build failed with exit code $LASTEXITCODE"
        }
        Write-Host "Built lig/ragflow-mcp:v0.26.4-1"
    }
    "ocr-build" {
        Assert-FreeSpace
        & docker build --file $ocrDockerfile --tag "lig/paddleocr-ko:v0.26.4-1" $ocrDirectory
        if ($LASTEXITCODE -ne 0) {
            throw "LIG Korean PaddleOCR Docker build failed with exit code $LASTEXITCODE"
        }
        Write-Host "Built lig/paddleocr-ko:v0.26.4-1"
    }
    "gpu-build" {
        Assert-FreeSpace
        & docker build --file $gpuUiDockerfile --tag "lig/ragflow-ui-gpu:v0.26.4-1" $workspaceDirectory
        if ($LASTEXITCODE -ne 0) {
            throw "LIG GPU UI runtime build failed with exit code $LASTEXITCODE"
        }
        & docker build --file $ocrDockerfile --build-arg "BASE_IMAGE=lig/ragflow-ui-gpu:v0.26.4-1" --tag "lig/paddleocr-ko-gpu:v0.26.4-1" $ocrDirectory
        if ($LASTEXITCODE -ne 0) {
            throw "LIG GPU Korean PaddleOCR build failed with exit code $LASTEXITCODE"
        }
        Write-Host "Built LIG CUDA 12.8 RAGFlow and Korean PaddleOCR images."
    }
    "embedding-build" {
        Assert-FreeSpace
        & docker build --file $embeddingModelDockerfile --tag "lig/qwen3-embedding-tei:0.6b-1" $embeddingDirectory
        if ($LASTEXITCODE -ne 0) {
            throw "Qwen3 TEI model image build failed with exit code $LASTEXITCODE"
        }
        & docker build --file $embeddingAdapterDockerfile --tag "lig/qwen3-embedding-adapter:0.6b-1" $embeddingDirectory
        if ($LASTEXITCODE -ne 0) {
            throw "Qwen3 embedding adapter image build failed with exit code $LASTEXITCODE"
        }
        Write-Host "Built Qwen3 Embedding 0.6B TEI CPU and query adapter images."
    }
    "build" {
        Assert-FreeSpace
        & docker build --file $uiDockerfile --tag "lig/ragflow-ui:v0.26.4-1" $workspaceDirectory
        if ($LASTEXITCODE -ne 0) { throw "LIG UI Docker build failed with exit code $LASTEXITCODE" }
        & docker build --file $mcpDockerfile --tag "lig/ragflow-mcp:v0.26.4-1" $mcpDirectory
        if ($LASTEXITCODE -ne 0) { throw "LIG management MCP Docker build failed with exit code $LASTEXITCODE" }
        & docker build --file $ocrDockerfile --tag "lig/paddleocr-ko:v0.26.4-1" $ocrDirectory
        if ($LASTEXITCODE -ne 0) { throw "LIG Korean PaddleOCR Docker build failed with exit code $LASTEXITCODE" }
        Write-Host "Built LIG UI, management MCP, and Korean PaddleOCR images."
    }
    "start" {
        Assert-LigConfiguration
        Assert-FreeSpace
        $configuration = Get-EnvFileValues $ligEnvFile
        $device = Get-ConfigurationValue $configuration "DEVICE" "cpu"
        if ($device -eq "gpu") {
            foreach ($image in @(
                (Get-ConfigurationValue $configuration "RAGFLOW_GPU_IMAGE"),
                (Get-ConfigurationValue $configuration "PADDLEOCR_GPU_IMAGE")
            )) {
                if ([string]::IsNullOrWhiteSpace($image)) {
                    throw "GPU image configuration is missing. Set RAGFLOW_GPU_IMAGE and PADDLEOCR_GPU_IMAGE."
                }
                & docker image inspect $image *> $null
                if ($LASTEXITCODE -ne 0) {
                    throw "Required GPU image is missing: $image. Run gpu-build or import the GPU air-gap bundle first."
                }
            }
        }
        & docker image inspect "lig/ragflow-mcp:v0.26.4-1" *> $null
        if ($LASTEXITCODE -ne 0) {
            if (-not (Test-Path -LiteralPath $mcpDockerfile -PathType Leaf)) {
                throw "Management MCP image is missing and its Dockerfile is unavailable: $mcpDockerfile"
            }
            & docker build --file $mcpDockerfile --tag "lig/ragflow-mcp:v0.26.4-1" $mcpDirectory
            if ($LASTEXITCODE -ne 0) { throw "LIG management MCP Docker build failed with exit code $LASTEXITCODE" }
        }
        & docker image inspect "lig/paddleocr-ko:v0.26.4-1" *> $null
        if ($LASTEXITCODE -ne 0) {
            if (-not (Test-Path -LiteralPath $ocrDockerfile -PathType Leaf)) {
                throw "Korean PaddleOCR image is missing and its Dockerfile is unavailable: $ocrDockerfile"
            }
            & docker build --file $ocrDockerfile --tag "lig/paddleocr-ko:v0.26.4-1" $ocrDirectory
            if ($LASTEXITCODE -ne 0) { throw "LIG Korean PaddleOCR Docker build failed with exit code $LASTEXITCODE" }
        }
        Invoke-Compose @("up", "-d", "--remove-orphans")
        Invoke-Compose @("ps")
    }
    "embedding-start" {
        Assert-FreeSpace
        foreach ($image in @("lig/qwen3-embedding-tei:0.6b-1", "lig/qwen3-embedding-adapter:0.6b-1")) {
            & docker image inspect $image *> $null
            if ($LASTEXITCODE -ne 0) {
                throw "Optional embedding image is missing: $image. Run embedding-build or import the air-gap bundle first."
            }
        }
        Invoke-Compose @("--profile", "embedding-cpu", "up", "-d", "qwen3-embedding-tei", "qwen3-embedding")
        Invoke-Compose @("--profile", "embedding-cpu", "ps", "qwen3-embedding-tei", "qwen3-embedding")
    }
    "embedding-stop" {
        Invoke-Compose @("--profile", "embedding-cpu", "stop", "qwen3-embedding", "qwen3-embedding-tei")
    }
    "embedding-status" {
        Invoke-Compose @("--profile", "embedding-cpu", "ps", "qwen3-embedding-tei", "qwen3-embedding")
    }
    "embedding-test" {
        $configuration = Get-EnvFileValues $ligEnvFile
        $binding = Get-ConfigurationValue $configuration "QWEN3_EMBEDDING_PORT" "127.0.0.1:42317"
        $port = ($binding -split ':')[-1]
        if ($port -notmatch '^\d+$') { throw "QWEN3_EMBEDDING_PORT must end with a numeric port. Current value: $binding" }
        $baseUrl = "http://127.0.0.1:$port"
        $health = $null
        for ($attempt = 1; $attempt -le 12; $attempt++) {
            try {
                $health = Invoke-RestMethod -Uri "$baseUrl/health" -TimeoutSec 10
                if ($health.status -eq "ok") { break }
            }
            catch {
                if ($attempt -eq 12) { throw }
            }
            Start-Sleep -Seconds 5
        }
        if ($health.status -ne "ok" -or $health.model -ne "Qwen/Qwen3-Embedding-0.6B") {
            throw "Unexpected embedding health response."
        }
        $body = @{ inputs = @("국방 문서 검색 시험", "defense document retrieval test") } | ConvertTo-Json -Compress
        $vectors = Invoke-RestMethod -Uri "$baseUrl/embed" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 120
        if (@($vectors).Count -ne 2 -or @($vectors[0]).Count -ne 1024 -or @($vectors[1]).Count -ne 1024) {
            throw "Embedding response must contain two 1024-dimensional vectors."
        }
        Write-Host "Qwen3 embedding health and 1024-dimensional batch inference passed."
    }
    "stop" { Invoke-Compose @("down") }
    "status" {
        Invoke-Compose @("ps")
        & docker system df
    }
    "diagnostics" { Invoke-Diagnostics }
    "logs" { Invoke-Compose @("logs", "--tail", "200") }
}
