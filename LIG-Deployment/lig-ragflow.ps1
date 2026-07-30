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
$persistentStateDirectory = Join-Path ([Environment]::GetFolderPath("LocalApplicationData")) "LIG-RAGFlow"
$persistentSecretFile = Join-Path $persistentStateDirectory ".env.secret"
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
    Ensure-LigSecrets
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

function Invoke-Docker([string[]]$Arguments) {
    $dockerExecutable = (Get-Command docker -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    $previousErrorActionPreference = $ErrorActionPreference
    $dockerExitCode = 1
    try {
        $ErrorActionPreference = "Continue"
        & $dockerExecutable @Arguments 2>&1 | ForEach-Object { Write-Host $_ }
        $dockerExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($dockerExitCode -ne 0) { throw "docker failed with exit code $dockerExitCode" }
}

function Invoke-DockerCapture([string[]]$Arguments, [switch]$AllowFailure) {
    $dockerExecutable = (Get-Command docker -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    $previousErrorActionPreference = $ErrorActionPreference
    $dockerExitCode = 1
    $output = @()
    try {
        $ErrorActionPreference = "Continue"
        $output = @(& $dockerExecutable @Arguments 2>&1 | ForEach-Object { $_.ToString() })
        $dockerExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($dockerExitCode -ne 0 -and -not $AllowFailure) {
        throw "docker failed with exit code $dockerExitCode"
    }
    return [pscustomobject]@{
        ExitCode = $dockerExitCode
        Lines = $output
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

function New-RandomSecret {
    $bytes = New-Object byte[] 32
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) }
    finally { $generator.Dispose() }
    return [Convert]::ToBase64String($bytes)
}

function Get-ExistingContainerEnvValue([string]$Name) {
    $containers = Invoke-DockerCapture -Arguments @(
        "ps", "-a", "--filter", "label=com.docker.compose.project=lig-ragflow", "--format", "{{.Names}}"
    ) -AllowFailure
    if ($containers.ExitCode -ne 0) { return $null }
    $orderedNames = @($containers.Lines | Where-Object { $_ -match 'ragflow-(worker-)?(cpu|gpu)' }) + @($containers.Lines)
    foreach ($containerName in $orderedNames | Select-Object -Unique) {
        $environment = Invoke-DockerCapture -Arguments @(
            "inspect", "--format", "{{range .Config.Env}}{{println .}}{{end}}", $containerName
        ) -AllowFailure
        if ($environment.ExitCode -ne 0) { continue }
        $prefix = "$Name="
        $entry = $environment.Lines | Where-Object { $_.StartsWith($prefix, [StringComparison]::Ordinal) } | Select-Object -First 1
        if ($entry) { return $entry.Substring($prefix.Length) }
    }
    return $null
}

function Ensure-LigSecrets {
    if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) {
        if (Test-Path -LiteralPath $persistentSecretFile -PathType Leaf) {
            Copy-Item -LiteralPath $persistentSecretFile -Destination $secretFile
        }
        else {
            Copy-Item -LiteralPath (Join-Path $deploymentDirectory ".env.secret.example") -Destination $secretFile
        }
    }
    elseif (Test-Path -LiteralPath $persistentSecretFile -PathType Leaf) {
        $localValues = Get-EnvFileValues $secretFile
        $localKey = $localValues["LIG_DOCUMENT_PASSWORD_KEY"]
        if ([string]::IsNullOrWhiteSpace($localKey) -or $localKey -eq "generate-a-base64-encoded-32-byte-key") {
            Copy-Item -LiteralPath $persistentSecretFile -Destination $secretFile -Force
        }
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
        $existingKey = Get-ExistingContainerEnvValue "LIG_DOCUMENT_PASSWORD_KEY"
        if ($existingKey) {
            if ($keyLineIndex -ge 0) { $lines[$keyLineIndex] = "LIG_DOCUMENT_PASSWORD_KEY=$existingKey" }
            else { $lines += "LIG_DOCUMENT_PASSWORD_KEY=$existingKey"; $keyLineIndex = $lines.Count - 1 }
            $currentValue = $existingKey
            Write-Host "Recovered the existing document password key from the LIG runtime."
        }
    }
    if ([string]::IsNullOrWhiteSpace($currentValue) -or $currentValue -eq "generate-a-base64-encoded-32-byte-key") {
        $keyLine = "LIG_DOCUMENT_PASSWORD_KEY=$(New-RandomSecret)"
        if ($keyLineIndex -ge 0) { $lines[$keyLineIndex] = $keyLine } else { $lines += $keyLine }
        Write-Host "Generated the local document password encryption key in LIG-Deployment\.env.secret."
    }
    if ($legacyKeyLineIndex -ge 0) { $lines = @($lines | Where-Object { $_ -notmatch '^\s*LIG_PDF_PASSWORD_KEY=' }) }
    if (-not ($lines | Where-Object { $_ -match '^\s*LIG_DOCUMENT_PASSWORD_KEY_ID=' })) {
        $existingKeyId = Get-ExistingContainerEnvValue "LIG_DOCUMENT_PASSWORD_KEY_ID"
        $lines += "LIG_DOCUMENT_PASSWORD_KEY_ID=$(if ($existingKeyId) { $existingKeyId } else { 'primary' })"
    }
    if (-not ($lines | Where-Object { $_ -match '^\s*LIG_DOCUMENT_PASSWORD_PREVIOUS_KEYS=' })) {
        $existingPreviousKeys = Get-ExistingContainerEnvValue "LIG_DOCUMENT_PASSWORD_PREVIOUS_KEYS"
        $lines += "LIG_DOCUMENT_PASSWORD_PREVIOUS_KEYS=$existingPreviousKeys"
    }
    $ocrTokenLineIndex = -1
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match '^\s*PADDLEOCR_INTERNAL_TOKEN=') { $ocrTokenLineIndex = $index }
    }
    $ocrToken = if ($ocrTokenLineIndex -ge 0) { ($lines[$ocrTokenLineIndex] -split '=', 2)[1].Trim() } else { "" }
    if ([string]::IsNullOrWhiteSpace($ocrToken) -or $ocrToken -eq "replace-with-a-random-internal-token") {
        $existingOcrToken = Get-ExistingContainerEnvValue "PADDLEOCR_INTERNAL_TOKEN"
        if ($existingOcrToken) {
            $ocrTokenLine = "PADDLEOCR_INTERNAL_TOKEN=$existingOcrToken"
            if ($ocrTokenLineIndex -ge 0) { $lines[$ocrTokenLineIndex] = $ocrTokenLine } else { $lines += $ocrTokenLine; $ocrTokenLineIndex = $lines.Count - 1 }
            $ocrToken = $existingOcrToken
            Write-Host "Recovered the existing internal PaddleOCR token from the LIG runtime."
        }
    }
    if ([string]::IsNullOrWhiteSpace($ocrToken) -or $ocrToken -eq "replace-with-a-random-internal-token") {
        $ocrTokenLine = "PADDLEOCR_INTERNAL_TOKEN=$(New-RandomSecret)"
        if ($ocrTokenLineIndex -ge 0) { $lines[$ocrTokenLineIndex] = $ocrTokenLine } else { $lines += $ocrTokenLine }
        Write-Host "Generated the internal PaddleOCR bearer token in LIG-Deployment\.env.secret."
    }
    [IO.File]::WriteAllLines($secretFile, $lines, [Text.UTF8Encoding]::new($false))
    if (-not (Test-Path -LiteralPath $persistentStateDirectory -PathType Container)) {
        New-Item -ItemType Directory -Path $persistentStateDirectory -Force | Out-Null
    }
    Copy-Item -LiteralPath $secretFile -Destination $persistentSecretFile -Force
}

function Assert-LigConfiguration {
    Ensure-LigSecrets
    $configuration = Get-EnvFileValues $ligEnvFile
    $workerValue = Get-ConfigurationValue $configuration "TASK_EXECUTOR_WORKERS" "1"
    $workers = 0
    if (-not [int]::TryParse($workerValue, [ref]$workers) -or $workers -lt 1) {
        throw "TASK_EXECUTOR_WORKERS must be a positive integer. Current value: $workerValue"
    }
    foreach ($settingName in @("DOC_BULK_SIZE", "EMBEDDING_BATCH_SIZE", "THREAD_POOL_MAX_WORKERS", "PADDLEOCR_JOB_WORKERS", "PADDLEOCR_TASK_PAGE_SIZE", "PADDLEOCR_MAX_PENDING_JOBS", "PADDLEOCR_MIN_FREE_BYTES", "PADDLEOCR_MAX_PAGE_PIXELS", "MAX_CONCURRENT_TASKS", "MAX_CONCURRENT_CHUNK_BUILDERS", "TASK_LEASE_SECONDS", "LIG_INGESTION_MEMORY_RESERVE_BYTES", "LIG_PDF_ESTIMATED_WORKING_BYTES_PER_PAGE", "PADDLEOCR_ESTIMATED_BYTES_PER_PIXEL")) {
        $settingValue = Get-ConfigurationValue $configuration $settingName
        if ([string]::IsNullOrWhiteSpace($settingValue)) { continue }
        [long]$parsed = 0
        if (-not [long]::TryParse($settingValue, [ref]$parsed) -or $parsed -lt 1) {
            throw "$settingName must be a positive integer. Current value: $settingValue"
        }
    }
    foreach ($settingName in @("MAX_CONTENT_LENGTH", "QUART_BODY_TIMEOUT", "LIG_DOCUMENT_MAX_BYTES", "PADDLEOCR_MAX_UPLOAD_BYTES", "PADDLEOCR_MAX_PDF_PAGES", "TASK_MAX_CRASH_RETRIES")) {
        $settingValue = Get-ConfigurationValue $configuration $settingName
        if ([string]::IsNullOrWhiteSpace($settingValue)) { continue }
        [long]$parsed = 0
        if (-not [long]::TryParse($settingValue, [ref]$parsed) -or $parsed -lt 0) {
            throw "$settingName must be zero (unlimited) or a positive integer. Current value: $settingValue"
        }
    }
    $memoryPercentValue = Get-ConfigurationValue $configuration "LIG_INGESTION_MEMORY_PERCENT" "25"
    [int]$memoryPercent = 0
    if (-not [int]::TryParse($memoryPercentValue, [ref]$memoryPercent) -or $memoryPercent -lt 1 -or $memoryPercent -gt 100) {
        throw "LIG_INGESTION_MEMORY_PERCENT must be an integer from 1 through 100. Current value: $memoryPercentValue"
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
    $apiReachable = $false
    $serviceHealth = $null
    $healthDetail = $null
    $apiError = $null
    $dockerVersionResult = Invoke-DockerCapture -Arguments @("version", "--format", "{{.Server.Version}}") -AllowFailure
    $dockerServerVersion = $dockerVersionResult.Lines
    $dockerError = if ($dockerVersionResult.ExitCode -eq 0) { $null } else { "Docker engine is unavailable." }

    try {
        $ping = Invoke-WebRequest -Uri "$apiBase/api/v1/system/ping" -UseBasicParsing -TimeoutSec 10
        $apiReachable = $ping.StatusCode -eq 200 -and $ping.Content.Trim() -eq "pong"
    }
    catch {
        $apiError = $_.Exception.Message
    }
    $hasUsableApiKey = $apiKey -and $apiKey -notmatch 'replace-with'
    if ($apiReachable -and $hasUsableApiKey) {
        try {
            $headers = @{ Authorization = "Bearer $apiKey" }
            $response = Invoke-RestMethod -Uri "$apiBase/api/v1/system/status" -Headers $headers -TimeoutSec 10
            $serviceHealth = $response.data
        }
        catch {
            $healthDetail = "Authenticated dependency status is unavailable: $($_.Exception.Message)"
        }
    }
    elseif ($apiReachable) {
        $healthDetail = "RAGFlow API is reachable; configure RAGFLOW_MCP_API_KEY for authenticated dependency details."
    }

    $composeResult = Invoke-DockerCapture -Arguments (@($composeArguments) + @("ps", "--format", "json")) -AllowFailure
    $composeRows = @($composeResult.Lines | ForEach-Object {
        try { $_ | ConvertFrom-Json } catch { $null }
    } | Where-Object { $null -ne $_ })

    $containerNames = @($composeRows | ForEach-Object { $_.Name } | Where-Object { $_ })
    $stats = @()
    if ($containerNames.Count -gt 0) {
        $statsResult = Invoke-DockerCapture -Arguments (@("stats", "--no-stream", "--format", "{{json .}}") + $containerNames) -AllowFailure
        $stats = @($statsResult.Lines | ForEach-Object {
            try { $_ | ConvertFrom-Json } catch { $null }
        } | Where-Object { $null -ne $_ })
    }

    $timingSamples = @()
    $recentErrors = @()
    $ragflowContainer = $containerNames | Where-Object { $_ -match 'ragflow-worker-(cpu|gpu)' } | Select-Object -First 1
    if (-not $ragflowContainer) {
        $ragflowContainer = $containerNames | Where-Object { $_ -match 'ragflow-(cpu|gpu)' } | Select-Object -First 1
    }
    $ragflowHostname = $null
    $ragflowWorkerId = $null
    if ($ragflowContainer) {
        $inspectResult = Invoke-DockerCapture -Arguments @("inspect", "--format", "{{.Config.Hostname}}", $ragflowContainer) -AllowFailure
        $ragflowHostname = $inspectResult.Lines | Select-Object -Last 1
        $commandResult = Invoke-DockerCapture -Arguments @("inspect", "--format", "{{json .Config.Cmd}}", $ragflowContainer) -AllowFailure
        if ($commandResult.ExitCode -eq 0) {
            try {
                $containerCommand = @($commandResult.Lines | Select-Object -Last 1 | ConvertFrom-Json)
                $hostIdArgument = $containerCommand | Where-Object { $_ -like '--host-id=*' } | Select-Object -First 1
                if ($hostIdArgument) {
                    $ragflowWorkerId = $hostIdArgument.Substring('--host-id='.Length)
                }
            }
            catch {
                $ragflowWorkerId = $null
            }
        }
        $logsResult = Invoke-DockerCapture -Arguments @("logs", "--tail", "2000", $ragflowContainer) -AllowFailure
        $logLines = $logsResult.Lines
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
                CurrentContainer = [bool](
                    ($ragflowWorkerId -and $_.Name -match "_$([regex]::Escape($ragflowWorkerId))_") -or
                    ($ragflowHostname -and $_.Name -match [regex]::Escape($ragflowHostname)) -or
                    $_.Name -match '^task_executor(?:_[a-z0-9-]+)*_lig-(cpu|gpu)-worker_'
                )
                SamplesInLast30Minutes = @($_.Value).Count
            }
        })
    }

    $report = [pscustomobject]@{
        GeneratedAt = (Get-Date).ToString("o")
        DockerServerVersion = $dockerServerVersion
        DockerError = $dockerError
        ApiReachable = $apiReachable
        Configuration = [pscustomobject]@{
            Device = Get-ConfigurationValue $configuration "DEVICE"
            ApiProxyScheme = Get-ConfigurationValue $configuration "API_PROXY_SCHEME" "python"
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
        HealthDetail = $healthDetail
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
        Invoke-Docker @("pull", "infiniflow/ragflow:v0.26.4")
        Invoke-Compose @("pull", "infinity", "mysql", "minio", "redis")
    }
    "ui-build" {
        Assert-FreeSpace
        Invoke-Docker @("build", "--file", $uiDockerfile, "--tag", "lig/ragflow-ui:v0.26.4-2", $workspaceDirectory)
        Write-Host "Built lig/ragflow-ui:v0.26.4-2"
    }
    "mcp-build" {
        Assert-FreeSpace
        Invoke-Docker @("build", "--file", $mcpDockerfile, "--tag", "lig/ragflow-mcp:v0.26.4-2", $mcpDirectory)
        Write-Host "Built lig/ragflow-mcp:v0.26.4-2"
    }
    "ocr-build" {
        Assert-FreeSpace
        Invoke-Docker @("build", "--file", $ocrDockerfile, "--tag", "lig/paddleocr-ko:v0.26.4-2", $ocrDirectory)
        Write-Host "Built lig/paddleocr-ko:v0.26.4-2"
    }
    "gpu-build" {
        Assert-FreeSpace
        Invoke-Docker @("build", "--file", $gpuUiDockerfile, "--tag", "lig/ragflow-ui-gpu:v0.26.4-2", $workspaceDirectory)
        Invoke-Docker @("build", "--file", $ocrDockerfile, "--build-arg", "BASE_IMAGE=lig/ragflow-ui-gpu:v0.26.4-2", "--tag", "lig/paddleocr-ko-gpu:v0.26.4-2", $ocrDirectory)
        Write-Host "Built LIG CUDA 12.8 RAGFlow and Korean PaddleOCR images."
    }
    "embedding-build" {
        Assert-FreeSpace
        Invoke-Docker @("build", "--file", $embeddingModelDockerfile, "--tag", "lig/qwen3-embedding-tei:0.6b-1", $embeddingDirectory)
        Invoke-Docker @("build", "--file", $embeddingAdapterDockerfile, "--tag", "lig/qwen3-embedding-adapter:0.6b-1", $embeddingDirectory)
        Write-Host "Built Qwen3 Embedding 0.6B TEI CPU and query adapter images."
    }
    "build" {
        Assert-FreeSpace
        Invoke-Docker @("build", "--file", $uiDockerfile, "--tag", "lig/ragflow-ui:v0.26.4-2", $workspaceDirectory)
        Invoke-Docker @("build", "--file", $mcpDockerfile, "--tag", "lig/ragflow-mcp:v0.26.4-2", $mcpDirectory)
        Invoke-Docker @("build", "--file", $ocrDockerfile, "--tag", "lig/paddleocr-ko:v0.26.4-2", $ocrDirectory)
        Write-Host "Built LIG UI, management MCP, and Korean PaddleOCR images."
    }
    "start" {
        Assert-LigConfiguration
        Assert-FreeSpace
        $configuration = Get-EnvFileValues $ligEnvFile
        $device = (Get-ConfigurationValue $configuration "DEVICE" "cpu").Trim().ToLowerInvariant()
        if ($device -notin @("cpu", "gpu")) {
            throw "DEVICE must be cpu or gpu. Current value: $device"
        }

        $ragflowImage = if ($device -eq "gpu") {
            Get-ConfigurationValue $configuration "RAGFLOW_GPU_IMAGE"
        } else {
            Get-ConfigurationValue $configuration "RAGFLOW_IMAGE"
        }
        $ocrImage = if ($device -eq "gpu") {
            Get-ConfigurationValue $configuration "PADDLEOCR_GPU_IMAGE"
        } else {
            Get-ConfigurationValue $configuration "PADDLEOCR_IMAGE"
        }
        $mcpImage = Get-ConfigurationValue $configuration "RAGFLOW_MCP_LIG_IMAGE" "lig/ragflow-mcp:v0.26.4-2"
        foreach ($requiredImage in @($ragflowImage, $ocrImage, $mcpImage)) {
            if ([string]::IsNullOrWhiteSpace($requiredImage)) {
                throw "Required $device image configuration is missing. Check RAGFLOW_IMAGE, RAGFLOW_GPU_IMAGE, PADDLEOCR_IMAGE, PADDLEOCR_GPU_IMAGE, and RAGFLOW_MCP_LIG_IMAGE."
            }
        }

        $ragflowImageInspect = Invoke-DockerCapture -Arguments @("image", "inspect", "--format", "{{.Id}}", $ragflowImage) -AllowFailure
        if ($ragflowImageInspect.ExitCode -ne 0) {
            if ($device -eq "gpu") {
                throw "Required GPU RAGFlow image is missing: $ragflowImage. Run gpu-build or import the GPU air-gap bundle first."
            }
            if (-not (Test-Path -LiteralPath $uiDockerfile -PathType Leaf)) {
                throw "RAGFlow image is missing and its Dockerfile is unavailable: $ragflowImage"
            }
            Invoke-Docker @("build", "--file", $uiDockerfile, "--tag", $ragflowImage, $workspaceDirectory)
        }

        $mcpImageInspect = Invoke-DockerCapture -Arguments @("image", "inspect", "--format", "{{.Id}}", $mcpImage) -AllowFailure
        if ($mcpImageInspect.ExitCode -ne 0) {
            if (-not (Test-Path -LiteralPath $mcpDockerfile -PathType Leaf)) {
                throw "Management MCP image is missing and its Dockerfile is unavailable: $mcpDockerfile"
            }
            Invoke-Docker @("build", "--file", $mcpDockerfile, "--tag", $mcpImage, $mcpDirectory)
        }
        $ocrImageInspect = Invoke-DockerCapture -Arguments @("image", "inspect", "--format", "{{.Id}}", $ocrImage) -AllowFailure
        if ($ocrImageInspect.ExitCode -ne 0) {
            if ($device -eq "gpu") {
                throw "Required GPU PaddleOCR image is missing: $ocrImage. Run gpu-build or import the GPU air-gap bundle first."
            }
            if (-not (Test-Path -LiteralPath $ocrDockerfile -PathType Leaf)) {
                throw "Korean PaddleOCR image is missing and its Dockerfile is unavailable: $ocrDockerfile"
            }
            Invoke-Docker @("build", "--file", $ocrDockerfile, "--build-arg", "BASE_IMAGE=$ragflowImage", "--tag", $ocrImage, $ocrDirectory)
        }
        # Start asynchronously. RAGFlow's health check verifies every backing
        # service and can remain in "Waiting" long after the containers have
        # started, which makes an otherwise successful start look hung.
        Invoke-Compose @("up", "-d", "--remove-orphans")
        Invoke-Compose @("ps")
    }
    "embedding-start" {
        Assert-FreeSpace
        foreach ($image in @("lig/qwen3-embedding-tei:0.6b-1", "lig/qwen3-embedding-adapter:0.6b-1")) {
            $imageInspect = Invoke-DockerCapture -Arguments @("image", "inspect", "--format", "{{.Id}}", $image) -AllowFailure
            if ($imageInspect.ExitCode -ne 0) {
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
        # Windows PowerShell 5.1 otherwise encodes a string request body with
        # the active ANSI code page. Send explicit UTF-8 bytes for Korean text.
        $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($body)
        $vectors = Invoke-RestMethod -Uri "$baseUrl/embed" -Method Post -ContentType "application/json; charset=utf-8" -Body $bodyBytes -TimeoutSec 120
        if (@($vectors).Count -ne 2 -or @($vectors[0]).Count -ne 1024 -or @($vectors[1]).Count -ne 1024) {
            throw "Embedding response must contain two 1024-dimensional vectors."
        }
        Write-Host "Qwen3 embedding health and 1024-dimensional batch inference passed."
    }
    "stop" { Invoke-Compose @("down") }
    "status" {
        Invoke-Compose @("ps")
        Invoke-Docker @("system", "df")
    }
    "diagnostics" { Invoke-Diagnostics }
    "logs" { Invoke-Compose @("logs", "--tail", "200") }
}
