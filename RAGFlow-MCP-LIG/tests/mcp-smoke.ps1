param(
    [string]$BaseUrl = "http://127.0.0.1:9380",
    [string]$ApiKey = $env:RAGFLOW_API_KEY,
    [switch]$Crud,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
if (-not ("System.Net.Http.HttpClient" -as [type])) { Add-Type -AssemblyName System.Net.Http }
if (-not $ApiKey) { throw "ApiKey or RAGFLOW_API_KEY is required" }
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $SkipBuild) {
    dotnet build (Join-Path $root "src\RagFlowMcp.csproj") -c Release
    if ($LASTEXITCODE -ne 0) { throw "Build failed" }
}

$start = [Diagnostics.ProcessStartInfo]::new("dotnet")
$start.WorkingDirectory = $root
$start.UseShellExecute = $false
$start.CreateNoWindow = $true
$start.Arguments = 'run --project "src/RagFlowMcp.csproj" -c Release --no-build'
$start.Environment["RAGFLOW_BASE_URL"] = $BaseUrl
$start.Environment["RAGFLOW_API_KEY"] = $ApiKey
$start.Environment["ASPNETCORE_URLS"] = "http://127.0.0.1:42220"
$process = [Diagnostics.Process]::Start($start)

function Invoke-Mcp([string]$Body, [string]$Session = "") {
    $client = [Net.Http.HttpClient]::new()
    $request = [Net.Http.HttpRequestMessage]::new([Net.Http.HttpMethod]::Post, "http://127.0.0.1:42220/mcp")
    try {
        [void]$request.Headers.TryAddWithoutValidation("Accept", "application/json, text/event-stream")
        if ($Session) { [void]$request.Headers.TryAddWithoutValidation("Mcp-Session-Id", $Session) }
        $request.Content = [Net.Http.StringContent]::new($Body, [Text.Encoding]::UTF8, "application/json")
        $response = $client.SendAsync($request).GetAwaiter().GetResult()
        try {
            $content = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
            if (-not $response.IsSuccessStatusCode) { throw "MCP HTTP $([int]$response.StatusCode): $content" }
            $sessionId = if ($response.Headers.Contains("Mcp-Session-Id")) { [string]($response.Headers.GetValues("Mcp-Session-Id") | Select-Object -First 1) } else { "" }
            [pscustomobject]@{ Content = $content; Session = $sessionId }
        } finally { $response.Dispose() }
    } finally { $request.Dispose(); $client.Dispose() }
}

function ConvertFrom-Mcp([string]$Content) {
    $line = $Content -split "`r?`n" | Where-Object { $_ -like "data: *" } | Select-Object -First 1
    if ($line) { return $line.Substring(6) | ConvertFrom-Json }
    return $Content | ConvertFrom-Json
}

try {
    $createdDatasetId = $null
    $health = $null
    foreach ($attempt in 1..60) {
        try { $health = Invoke-RestMethod "http://127.0.0.1:42220/healthz" -TimeoutSec 2; break }
        catch { if ($process.HasExited) { throw "Adapter exited: $($process.ExitCode)" }; Start-Sleep -Milliseconds 500 }
    }
    if (-not $health -or $health.status -ne "ok") { throw "Adapter health check failed" }

    $initialize = @{ jsonrpc="2.0"; id=1; method="initialize"; params=@{ protocolVersion="2025-06-18"; capabilities=@{}; clientInfo=@{ name="ragflow-smoke"; version="1.0" } } } | ConvertTo-Json -Depth 10 -Compress
    $initResponse = Invoke-Mcp $initialize
    if (-not $initResponse.Session) { throw "No MCP session ID" }
    $toolsResponse = Invoke-Mcp (@{ jsonrpc="2.0"; id=2; method="tools/list"; params=@{} } | ConvertTo-Json -Compress) $initResponse.Session
    $tools = ConvertFrom-Mcp $toolsResponse.Content
    $names = @($tools.result.tools.name)
    foreach ($required in @("rag_flow_config", "create_rag_flow_dataset", "upload_rag_flow_document", "start_rag_flow_parsing", "update_rag_flow_chunk", "delete_rag_flow_dataset")) {
        if ($required -notin $names) { throw "Missing tool: $required" }
    }

    $call = @{ jsonrpc="2.0"; id=3; method="tools/call"; params=@{ name="list_rag_flow_datasets"; arguments=@{ page=1; pageSize=10 } } } | ConvertTo-Json -Depth 10 -Compress
    $callResult = ConvertFrom-Mcp (Invoke-Mcp $call $initResponse.Session).Content
    if ($callResult.error -or $callResult.result.isError) { throw "Live list call failed: $($callResult | ConvertTo-Json -Depth 10 -Compress)" }

    if ($Crud) {
        function Invoke-Tool([int]$Id, [string]$Name, [hashtable]$Arguments) {
            $body = @{ jsonrpc="2.0"; id=$Id; method="tools/call"; params=@{ name=$Name; arguments=$Arguments } } | ConvertTo-Json -Depth 20 -Compress
            $result = ConvertFrom-Mcp (Invoke-Mcp $body $initResponse.Session).Content
            if ($result.error -or $result.result.isError) { throw "$Name failed: $($result | ConvertTo-Json -Depth 10 -Compress)" }
            $text = [string]($result.result.content | Where-Object type -eq "text" | Select-Object -First 1).text
            if ($text) { return $text | ConvertFrom-Json }
        }

        $suffix = [guid]::NewGuid().ToString("N").Substring(0, 8)
        $dataset = Invoke-Tool 10 "create_rag_flow_dataset" @{ name="LIG MCP CRUD $suffix"; description="temporary MCP smoke dataset"; chunkTokenNum=128 }
        $createdDatasetId = $dataset.data.id
        if (-not $createdDatasetId) { throw "Dataset ID missing" }
        $updated = Invoke-Tool 11 "update_rag_flow_dataset" @{ datasetId=$createdDatasetId; description="updated by MCP smoke" }
        if ($updated.code -ne 0) { throw "Dataset update failed" }
        $fixture = Join-Path $PSScriptRoot "fixture-ko.txt"
        $upload = Invoke-Tool 12 "upload_rag_flow_document" @{ datasetId=$createdDatasetId; filePath=$fixture }
        $documentId = @($upload.data)[0].id
        if (-not $documentId) { throw "Document ID missing" }
        Invoke-Tool 13 "start_rag_flow_parsing" @{ datasetId=$createdDatasetId; documentIds=@($documentId) } | Out-Null

        $document = $null
        foreach ($attempt in 1..120) {
            $documents = Invoke-Tool (20 + $attempt) "list_rag_flow_documents" @{ datasetId=$createdDatasetId; page=1; pageSize=10 }
            $document = @($documents.data.docs | Where-Object id -eq $documentId)[0]
            if ($document.run -eq "DONE") { break }
            if ($document.run -eq "FAIL") { throw "Fixture parsing failed: $($document.progress_msg)" }
            Start-Sleep -Seconds 1
        }
        if ($document.run -ne "DONE") { throw "Fixture parsing timeout" }
        $chunks = Invoke-Tool 150 "list_rag_flow_chunks" @{ datasetId=$createdDatasetId; documentId=$documentId; page=1; pageSize=100 }
        $chunk = @($chunks.data.chunks)[0]
        if (-not $chunk.id) { throw "No fixture chunks" }
        Invoke-Tool 151 "update_rag_flow_chunk" @{ datasetId=$createdDatasetId; documentId=$documentId; chunkId=$chunk.id; content=($chunk.content + " CRUD-MARKER") } | Out-Null
        Invoke-Tool 152 "delete_rag_flow_chunks" @{ datasetId=$createdDatasetId; documentId=$documentId; chunkIds=@($chunk.id) } | Out-Null
        Invoke-Tool 153 "delete_rag_flow_documents" @{ datasetId=$createdDatasetId; documentIds=@($documentId) } | Out-Null
        Invoke-Tool 154 "delete_rag_flow_dataset" @{ datasetId=$createdDatasetId } | Out-Null
        $createdDatasetId = $null
    }

    [pscustomobject]@{ status="passed"; tools=$names.Count; liveListCall=$true; crud=[bool]$Crud; health=$health.status } | ConvertTo-Json -Compress
}
finally {
    if ($createdDatasetId) {
        try {
            $cleanup = @{ jsonrpc="2.0"; id=999; method="tools/call"; params=@{ name="delete_rag_flow_dataset"; arguments=@{ datasetId=$createdDatasetId } } } | ConvertTo-Json -Depth 10 -Compress
            Invoke-Mcp $cleanup $initResponse.Session | Out-Null
        } catch { }
    }
    if ($process -and -not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue; $process.WaitForExit() }
}
