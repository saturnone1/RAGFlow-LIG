param(
    [ValidateSet("config", "pull", "start", "model", "stop", "status", "logs")]
    [string]$Action = "status"
)

$ErrorActionPreference = "Stop"
$dockerDirectory = $PSScriptRoot
$composeArguments = @(
    "compose",
    "--project-name", "lig-ragflow",
    "--project-directory", $dockerDirectory,
    "--env-file", (Join-Path $dockerDirectory ".env"),
    "--env-file", (Join-Path $dockerDirectory ".env.lig")
)
$secretFile = Join-Path $dockerDirectory ".env.secret"
if (Test-Path -LiteralPath $secretFile) { $composeArguments += @("--env-file", $secretFile) }
$composeArguments += @(
    "-f", (Join-Path $dockerDirectory "docker-compose.yml"),
    "-f", (Join-Path $dockerDirectory "docker-compose.lig.yml")
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
        Invoke-Compose @("pull")
    }
    "start" {
        Assert-FreeSpace
        Invoke-Compose @("up", "-d", "--remove-orphans")
        Invoke-Compose @("ps")
    }
    "model" {
        Assert-FreeSpace
        $model = if ($env:OLLAMA_EMBEDDING_MODEL) { $env:OLLAMA_EMBEDDING_MODEL } else { "qwen3-embedding:0.6b" }
        Invoke-Compose @("exec", "ollama", "ollama", "pull", $model)
        Invoke-Compose @("exec", "ollama", "ollama", "show", $model)
    }
    "stop" { Invoke-Compose @("down") }
    "status" {
        Invoke-Compose @("ps")
        & docker system df
    }
    "logs" { Invoke-Compose @("logs", "--tail", "200") }
}
