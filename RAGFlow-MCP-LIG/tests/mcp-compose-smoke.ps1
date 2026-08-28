param(
    [string]$McpUrl = "http://127.0.0.1:42306/mcp",
    [string]$HealthUrl = "http://127.0.0.1:42306/healthz",
    [string]$ApiKey = $env:RAGFLOW_API_KEY,
    [string]$MountedDataDirectory = (Join-Path $PSScriptRoot "..\..\LIG-Deployment\mcp-files"),
    [switch]$GenericUpload
)

$ErrorActionPreference = "Stop"
if (-not $ApiKey) { throw "ApiKey or RAGFLOW_API_KEY is required" }
$stagedFixture = $null

function Invoke-Mcp([string]$Body, [string]$Session = "", [switch]$WithoutAuthentication) {
    $client = [Net.Http.HttpClient]::new()
    $request = [Net.Http.HttpRequestMessage]::new([Net.Http.HttpMethod]::Post, $McpUrl)
    try {
        [void]$request.Headers.TryAddWithoutValidation("Accept", "application/json, text/event-stream")
        if (-not $WithoutAuthentication) { [void]$request.Headers.TryAddWithoutValidation("Authorization", "Bearer $ApiKey") }
        if ($Session) { [void]$request.Headers.TryAddWithoutValidation("Mcp-Session-Id", $Session) }
        $request.Content = [Net.Http.StringContent]::new($Body, [Text.Encoding]::UTF8, "application/json")
        $response = $client.SendAsync($request).GetAwaiter().GetResult()
        try {
            $content = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
            if (-not $response.IsSuccessStatusCode) { throw "MCP HTTP $([int]$response.StatusCode): $content" }
            $sessionId = if ($response.Headers.Contains("Mcp-Session-Id")) { [string]($response.Headers.GetValues("Mcp-Session-Id") | Select-Object -First 1) } else { "" }
            [pscustomobject]@{ Content = $content; Session = $sessionId }
        }
        finally { $response.Dispose() }
    }
    finally { $request.Dispose(); $client.Dispose() }
}

function ConvertFrom-Mcp([string]$Content) {
    $line = $Content -split "`r?`n" | Where-Object { $_ -like "data: *" } | Select-Object -First 1
    if ($line) { return $line.Substring(6) | ConvertFrom-Json }
    return $Content | ConvertFrom-Json
}

$health = Invoke-RestMethod $HealthUrl -TimeoutSec 5
if ($health.status -ne "ok" -or $health.ragflowBaseUrl -ne "http://ragflow-runtime:9380") { throw "Compose MCP health check failed" }

try {
    Invoke-Mcp '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"compose-unauthenticated-test","version":"1"}}}' "" -WithoutAuthentication | Out-Null
    throw "Unauthenticated Compose MCP request unexpectedly succeeded"
}
catch {
    if ($_.Exception.Message -notmatch "MCP HTTP 401") { throw }
}

$initialize = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"compose-smoke","version":"1"}}}'
$initResponse = Invoke-Mcp $initialize
if (-not $initResponse.Session) { throw "No MCP session ID" }
$tools = ConvertFrom-Mcp (Invoke-Mcp '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' $initResponse.Session).Content
if (@($tools.result.tools).Count -ne 23) { throw "Expected 23 MCP tools" }

$versionCall = '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"rag_flow_api_request","arguments":{"method":"GET","relativePath":"api/v1/system/version"}}}'
$version = ConvertFrom-Mcp (Invoke-Mcp $versionCall $initResponse.Session).Content
if ($version.error -or $version.result.isError) { throw "Compose MCP RAGFlow version call failed" }

$summaryCall = '{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"list_rag_flow_dataset_summaries","arguments":{"page":1,"pageSize":5}}}'
$summaryResult = ConvertFrom-Mcp (Invoke-Mcp $summaryCall $initResponse.Session).Content
if ($summaryResult.error -or $summaryResult.result.isError) { throw "Lightweight dataset summary call failed" }
$summaryPayload = ([string]($summaryResult.result.content | Where-Object type -eq "text" | Select-Object -First 1).text) | ConvertFrom-Json
$firstDataset = @($summaryPayload.data) | Select-Object -First 1
$documentProjectionTested = $false
if ($firstDataset.id) {
    $documentCall = @{ jsonrpc="2.0"; id=7; method="tools/call"; params=@{ name="get_rag_flow_dataset_processing_status"; arguments=@{ datasetId=$firstDataset.id; page=1; pageSize=5 } } } | ConvertTo-Json -Depth 10 -Compress
    $documentResult = ConvertFrom-Mcp (Invoke-Mcp $documentCall $initResponse.Session).Content
    if ($documentResult.error -or $documentResult.result.isError) { throw "Lightweight document status call failed" }
    $documentProjectionTested = $true
}

$uploadedFileId = $null
try {
    if ($GenericUpload) {
        $mountedDirectory = [IO.Path]::GetFullPath($MountedDataDirectory)
        [IO.Directory]::CreateDirectory($mountedDirectory) | Out-Null
        $stagedFixture = Join-Path $mountedDirectory "fixture-ko.txt"
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot "fixture-ko.txt") -Destination $stagedFixture -Force

        $uploadCall = @{ jsonrpc="2.0"; id=4; method="tools/call"; params=@{ name="upload_rag_flow_api_files"; arguments=@{ relativePath="api/v1/files"; filePaths=@("/data/fixture-ko.txt"); fieldName="file" } } } | ConvertTo-Json -Depth 10 -Compress
        $uploadResult = ConvertFrom-Mcp (Invoke-Mcp $uploadCall $initResponse.Session).Content
        if ($uploadResult.error -or $uploadResult.result.isError) { throw "Compose MCP mounted-file upload failed" }
        $uploadPayload = ([string]($uploadResult.result.content | Where-Object type -eq "text" | Select-Object -First 1).text) | ConvertFrom-Json
        $uploadedFileId = @($uploadPayload.data)[0].id
        if (-not $uploadedFileId) { throw "Compose MCP upload returned no file ID" }

        $deleteBody = @{ ids=@($uploadedFileId) } | ConvertTo-Json -Compress
        $deleteCall = @{ jsonrpc="2.0"; id=5; method="tools/call"; params=@{ name="rag_flow_api_request"; arguments=@{ method="DELETE"; relativePath="api/v1/files"; bodyJson=$deleteBody } } } | ConvertTo-Json -Depth 10 -Compress
        $deleteResult = ConvertFrom-Mcp (Invoke-Mcp $deleteCall $initResponse.Session).Content
        if ($deleteResult.error -or $deleteResult.result.isError) { throw "Compose MCP upload cleanup failed" }
        $uploadedFileId = $null
    }
}
finally {
    if ($uploadedFileId) {
        try {
            $cleanupBody = @{ ids=@($uploadedFileId) } | ConvertTo-Json -Compress
            $cleanup = @{ jsonrpc="2.0"; id=99; method="tools/call"; params=@{ name="rag_flow_api_request"; arguments=@{ method="DELETE"; relativePath="api/v1/files"; bodyJson=$cleanupBody } } } | ConvertTo-Json -Depth 10 -Compress
            Invoke-Mcp $cleanup $initResponse.Session | Out-Null
        } catch { }
    }
    if ($stagedFixture) {
        Remove-Item -LiteralPath $stagedFixture -Force -ErrorAction SilentlyContinue
    }
}

[pscustomobject]@{
    status = "passed"
    tools = 23
    authentication = $true
    ragflowNetwork = $health.ragflowBaseUrl
    versionCall = $true
    lightweightDatasetSummary = $true
    lightweightDocumentStatus = $documentProjectionTested
    mountedFileUpload = [bool]$GenericUpload
} | ConvertTo-Json -Compress
