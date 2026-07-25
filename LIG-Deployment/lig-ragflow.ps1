param(
    [ValidateSet("config", "pull", "build", "ui-build", "mcp-build", "start", "model", "stop", "status", "diagnostics", "logs")]
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
$mcpDirectory = Join-Path $workspaceDirectory "RAGFlow-MCP-LIG"
$mcpDockerfile = Join-Path $mcpDirectory "Dockerfile"

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
if (Test-Path -LiteralPath $secretFile) { $composeArguments += @("--env-file", $secretFile) }
$composeArguments += @(
    "-f", (Join-Path $dockerDirectory "docker-compose.yml"),
    "-f", (Join-Path $deploymentDirectory "docker-compose.lig.yml")
)

function Invoke-Compose([string[]]$Arguments) {
    & docker @composeArguments @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed with exit code $LASTEXITCODE"
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

function Assert-LigConfiguration {
    $configuration = Get-EnvFileValues $ligEnvFile
    $workerValue = Get-ConfigurationValue $configuration "TASK_EXECUTOR_WORKERS" "1"
    $workers = 0
    if (-not [int]::TryParse($workerValue, [ref]$workers) -or $workers -lt 1 -or $workers -gt 16) {
        throw "TASK_EXECUTOR_WORKERS must be an integer between 1 and 16. Current value: $workerValue"
    }
    foreach ($setting in @(
        @{ Name = "DOC_BULK_SIZE"; Minimum = 1; Maximum = 64 },
        @{ Name = "EMBEDDING_BATCH_SIZE"; Minimum = 1; Maximum = 256 },
        @{ Name = "THREAD_POOL_MAX_WORKERS"; Minimum = 1; Maximum = 256 }
    )) {
        $settingValue = Get-ConfigurationValue $configuration $setting.Name
        if ($null -eq $settingValue) { continue }
        $parsed = 0
        if (-not [int]::TryParse($settingValue, [ref]$parsed) -or $parsed -lt $setting.Minimum -or $parsed -gt $setting.Maximum) {
            throw "$($setting.Name) must be between $($setting.Minimum) and $($setting.Maximum). Current value: $settingValue"
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
    $apiBase = "http://127.0.0.1:42201"
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
    $ragflowContainer = $containerNames | Where-Object { $_ -match 'ragflow-cpu' } | Select-Object -First 1
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
            EmbeddingMode = if ((Get-ConfigurationValue $configuration "COMPOSE_PROFILES") -match 'ollama') { "ollama profile" } else { "configured in RAGFlow (external provider)" }
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
    "build" {
        Assert-FreeSpace
        & docker build --file $uiDockerfile --tag "lig/ragflow-ui:v0.26.4-1" $workspaceDirectory
        if ($LASTEXITCODE -ne 0) { throw "LIG UI Docker build failed with exit code $LASTEXITCODE" }
        & docker build --file $mcpDockerfile --tag "lig/ragflow-mcp:v0.26.4-1" $mcpDirectory
        if ($LASTEXITCODE -ne 0) { throw "LIG management MCP Docker build failed with exit code $LASTEXITCODE" }
        Write-Host "Built LIG UI and management MCP images."
    }
    "start" {
        Assert-LigConfiguration
        Assert-FreeSpace
        & docker image inspect "lig/ragflow-mcp:v0.26.4-1" *> $null
        if ($LASTEXITCODE -ne 0) {
            if (-not (Test-Path -LiteralPath $mcpDockerfile -PathType Leaf)) {
                throw "Management MCP image is missing and its Dockerfile is unavailable: $mcpDockerfile"
            }
            & docker build --file $mcpDockerfile --tag "lig/ragflow-mcp:v0.26.4-1" $mcpDirectory
            if ($LASTEXITCODE -ne 0) { throw "LIG management MCP Docker build failed with exit code $LASTEXITCODE" }
        }
        Invoke-Compose @("up", "-d", "--remove-orphans")
        Invoke-Compose @("ps")
    }
    "model" {
        Assert-FreeSpace
        $model = if ($env:OLLAMA_EMBEDDING_MODEL) { $env:OLLAMA_EMBEDDING_MODEL } else { "qwen3-embedding:0.6b" }
        Invoke-Compose @("--profile", "ollama", "up", "-d", "ollama")
        Invoke-Compose @("--profile", "ollama", "exec", "ollama", "ollama", "pull", $model)
        Invoke-Compose @("--profile", "ollama", "exec", "ollama", "ollama", "show", $model)
    }
    "stop" { Invoke-Compose @("down") }
    "status" {
        Invoke-Compose @("ps")
        & docker system df
    }
    "diagnostics" { Invoke-Diagnostics }
    "logs" { Invoke-Compose @("logs", "--tail", "200") }
}
