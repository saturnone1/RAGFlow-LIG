param(
    [ValidateSet("config", "pull", "build", "ui-build", "mcp-build", "start", "model", "stop", "status", "logs")]
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

switch ($Action) {
    "config" {
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
    "logs" { Invoke-Compose @("logs", "--tail", "200") }
}
