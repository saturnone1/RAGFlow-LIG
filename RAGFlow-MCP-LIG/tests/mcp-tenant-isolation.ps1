param(
    [int]$McpPort = 42222,
    [int]$MockApiPort = 42391
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$project = Join-Path $root "src\RagFlowMcp.csproj"
$output = Join-Path ([IO.Path]::GetTempPath()) "lig-ragflow-mcp-tenant-test"
$dll = Join-Path $output "LigRagFlowMcp.dll"

& dotnet build $project --no-restore /p:UseAppHost=false "/p:OutputPath=$output\"
if ($LASTEXITCODE -ne 0) { throw "MCP test build failed" }

$mockScript = {
    param([int]$Port)
    $listener = [Net.HttpListener]::new()
    $listener.Prefixes.Add("http://127.0.0.1:$Port/")
    $listener.Start()
    try {
        while ($listener.IsListening) {
            $context = $listener.GetContext()
            if ($context.Request.Url.AbsolutePath -eq "/__shutdown") {
                $context.Response.StatusCode = 204
                $context.Response.Close()
                break
            }
            $authorization = [string]$context.Request.Headers["Authorization"]
            $token = if ($authorization.StartsWith("Bearer ", [StringComparison]::OrdinalIgnoreCase)) {
                $authorization.Substring(7).Trim()
            } else { "missing" }
            if ($token -eq "ragflow-alpha") {
                Start-Sleep -Milliseconds 200
            }
            $payload = @{
                code = 0
                data = @(@{ id = "dataset-$token"; name = "$token-private" })
                total = 1
            } | ConvertTo-Json -Depth 5 -Compress
            $bytes = [Text.Encoding]::UTF8.GetBytes($payload)
            $context.Response.StatusCode = 200
            $context.Response.ContentType = "application/json"
            $context.Response.ContentLength64 = $bytes.Length
            $context.Response.OutputStream.Write($bytes, 0, $bytes.Length)
            $context.Response.Close()
        }
    }
    finally {
        if ($listener.IsListening) { $listener.Stop() }
        $listener.Close()
    }
}

$mockPowerShell = [PowerShell]::Create()
[void]$mockPowerShell.AddScript($mockScript).AddArgument($MockApiPort)
$mockRun = $mockPowerShell.BeginInvoke()

$start = [Diagnostics.ProcessStartInfo]::new("dotnet", "`"$dll`"")
$start.UseShellExecute = $false
$start.CreateNoWindow = $true
$start.Environment["ASPNETCORE_URLS"] = "http://127.0.0.1:$McpPort"
$start.Environment["RAGFLOW_BASE_URL"] = "http://127.0.0.1:$MockApiPort"
$process = [Diagnostics.Process]::Start($start)
$client = [Net.Http.HttpClient]::new()

function ConvertFrom-Mcp([string]$Content) {
    $data = @($Content -split "`r?`n" | Where-Object { $_ -like "data: *" } | ForEach-Object { $_.Substring(6) })
    if ($data.Count) { return $data[-1] | ConvertFrom-Json }
    return $Content | ConvertFrom-Json
}

function Start-McpRequest([string]$Token, [string]$Body, [string]$Session = "") {
    $request = [Net.Http.HttpRequestMessage]::new([Net.Http.HttpMethod]::Post, "http://127.0.0.1:$McpPort/mcp")
    [void]$request.Headers.TryAddWithoutValidation("Accept", "application/json, text/event-stream")
    [void]$request.Headers.TryAddWithoutValidation("Authorization", "Bearer $Token")
    if ($Session) { [void]$request.Headers.TryAddWithoutValidation("Mcp-Session-Id", $Session) }
    $request.Content = [Net.Http.StringContent]::new($Body, [Text.Encoding]::UTF8, "application/json")
    return [pscustomobject]@{ Request = $request; Task = $client.SendAsync($request) }
}

function Complete-McpRequest($Pending) {
    try {
        $response = $Pending.Task.GetAwaiter().GetResult()
        $content = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        if (-not $response.IsSuccessStatusCode) { throw "MCP HTTP $([int]$response.StatusCode): $content" }
        return [pscustomobject]@{ Content = $content; Session = [string]$response.Headers.GetValues("Mcp-Session-Id") }
    }
    finally { $Pending.Request.Dispose() }
}

function Invoke-Mcp([string]$Token, [string]$Body, [string]$Session = "") {
    return Complete-McpRequest (Start-McpRequest $Token $Body $Session)
}

function Initialize-McpSession([string]$Token) {
    $initialize = @{ jsonrpc = "2.0"; id = 1; method = "initialize"; params = @{ protocolVersion = "2025-06-18"; capabilities = @{}; clientInfo = @{ name = "tenant-isolation-test"; version = "1" } } } | ConvertTo-Json -Depth 8 -Compress
    $initialized = Invoke-Mcp $Token $initialize
    if (-not $initialized.Session) { throw "MCP session was not created for $Token" }
    return $initialized.Session
}

try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 250
        try {
            Invoke-WebRequest "http://127.0.0.1:$McpPort/healthz" -UseBasicParsing -TimeoutSec 1 | Out-Null
            $ready = $true
            break
        }
        catch {
            if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 503) {
                $ready = $true
                break
            }
        }
    }
    if (-not $ready) { throw "MCP did not start" }

    $alphaSession = Initialize-McpSession "ragflow-alpha"
    $betaSession = Initialize-McpSession "ragflow-beta"
    $call = @{ jsonrpc = "2.0"; id = 2; method = "tools/call"; params = @{ name = "list_rag_flow_datasets"; arguments = @{ page = 1; pageSize = 10 } } } | ConvertTo-Json -Depth 8 -Compress
    $alphaPending = Start-McpRequest "ragflow-alpha" $call $alphaSession
    $betaPending = Start-McpRequest "ragflow-beta" $call $betaSession
    $alphaResult = ConvertFrom-Mcp (Complete-McpRequest $alphaPending).Content
    $betaResult = ConvertFrom-Mcp (Complete-McpRequest $betaPending).Content
    if ($alphaResult.error -or $alphaResult.result.isError) { throw "Dataset tool failed for ragflow-alpha" }
    if ($betaResult.error -or $betaResult.result.isError) { throw "Dataset tool failed for ragflow-beta" }
    $alpha = [string]($alphaResult.result.content | Where-Object type -eq "text" | Select-Object -First 1).text | ConvertFrom-Json
    $beta = [string]($betaResult.result.content | Where-Object type -eq "text" | Select-Object -First 1).text | ConvertFrom-Json
    if ($alpha.data[0].id -ne "dataset-ragflow-alpha") { throw "Alpha received another tenant's dataset" }
    if ($beta.data[0].id -ne "dataset-ragflow-beta") { throw "Beta received another tenant's dataset" }
    if ($alpha.data[0].id -eq $beta.data[0].id) { throw "Tenant dataset results were shared" }
    Write-Host "PASS: concurrent custom MCP calls forwarded each caller's Bearer token and isolated dataset results."
}
finally {
    $client.Dispose()
    if ($process -and -not $process.HasExited) {
        $process.Kill($true)
        $process.WaitForExit()
    }
    try { Invoke-WebRequest "http://127.0.0.1:$MockApiPort/__shutdown" -UseBasicParsing -TimeoutSec 2 | Out-Null }
    catch { }
    try { $mockPowerShell.EndInvoke($mockRun) | Out-Null }
    catch { }
    $mockPowerShell.Dispose()
}
