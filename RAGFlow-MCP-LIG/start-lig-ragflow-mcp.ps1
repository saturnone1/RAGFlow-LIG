param(
    [switch]$Restart,
    [switch]$ReadOnly,
    [switch]$EnableFileDownloads
)

function Start-LigRagFlowMcp {
$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$secretFile = Join-Path $projectRoot "LIG-Deployment\.env.secret"
$adapter = Join-Path $PSScriptRoot "src\bin\Release\net8.0\LigRagFlowMcp.exe"

$listener = Get-NetTCPConnection -LocalPort 42206 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
    if ($owner.Name -ne "LigRagFlowMcp.exe" -or $owner.ExecutablePath -notlike "*$projectRoot*") {
        throw "Port 42206 is owned by an unexpected process: $($owner.Name)"
    }
    if (-not $Restart) {
        Write-Host "LIG RAGFlow management MCP is already running (PID $($listener.OwningProcess))."
        return
    }
    Stop-Process -Id $listener.OwningProcess -Force
}

if (-not (Test-Path -LiteralPath $adapter)) {
    dotnet build (Join-Path $PSScriptRoot "src\RagFlowMcp.csproj") -c Release
    if ($LASTEXITCODE -ne 0) { throw "Management MCP build failed." }
}
if (-not (Test-Path -LiteralPath $secretFile)) { throw "Secret file not found: $secretFile" }

$secretLine = Get-Content -LiteralPath $secretFile | Where-Object { $_ -match "^RAGFLOW_MCP_API_KEY=" } | Select-Object -First 1
$apiKey = ($secretLine -split "=", 2)[1]
if (-not $apiKey -or $apiKey -eq "bootstrap-pending-ragflow-api-key") { throw "A real RAGFlow API key is required in LIG-Deployment/.env.secret." }

$start = [Diagnostics.ProcessStartInfo]::new($adapter)
$start.WorkingDirectory = $PSScriptRoot
$start.UseShellExecute = $false
$start.CreateNoWindow = $true
$start.Environment["RAGFLOW_BASE_URL"] = "http://127.0.0.1:42301"
$start.Environment["RAGFLOW_API_KEY"] = $apiKey
$start.Environment["RAGFLOW_WRITES_ENABLED"] = if ($ReadOnly) { "false" } elseif ($env:RAGFLOW_WRITES_ENABLED) { $env:RAGFLOW_WRITES_ENABLED } else { "true" }
$start.Environment["RAGFLOW_FILE_WRITES_ENABLED"] = if ($EnableFileDownloads) { "true" } elseif ($env:RAGFLOW_FILE_WRITES_ENABLED) { $env:RAGFLOW_FILE_WRITES_ENABLED } else { "false" }
if ($env:LIG_MCP_API_KEY) { $start.Environment["LIG_MCP_API_KEY"] = $env:LIG_MCP_API_KEY }
$start.Environment["ASPNETCORE_URLS"] = "http://127.0.0.1:42206"
$process = [Diagnostics.Process]::Start($start)

foreach ($attempt in 1..30) {
    try {
        $health = Invoke-RestMethod "http://127.0.0.1:42206/healthz" -TimeoutSec 2
        Write-Host "LIG RAGFlow management MCP started (PID $($process.Id), RAGFlow status: $($health.status))."
        return
    }
    catch {
        if ($process.HasExited) { throw "Management MCP exited with code $($process.ExitCode)." }
        Start-Sleep -Milliseconds 500
    }
}
throw "Management MCP did not become ready."
}

Start-LigRagFlowMcp
