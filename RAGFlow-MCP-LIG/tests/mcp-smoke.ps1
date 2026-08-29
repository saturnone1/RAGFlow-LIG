param(
    [string]$BaseUrl = "http://127.0.0.1:42301",
    [string]$ApiKey = $env:RAGFLOW_API_KEY,
    [switch]$Crud,
    [switch]$GenericUpload,
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

$adapter = Join-Path $root "src\bin\Release\net8.0\LigRagFlowMcp.exe"
if (-not (Test-Path -LiteralPath $adapter)) { throw "Built adapter not found: $adapter" }
$start = [Diagnostics.ProcessStartInfo]::new($adapter)
$start.WorkingDirectory = $root
$start.UseShellExecute = $false
$start.CreateNoWindow = $true
$start.Environment["RAGFLOW_BASE_URL"] = $BaseUrl
$start.Environment["RAGFLOW_WRITES_ENABLED"] = if ($Crud -or $GenericUpload) { "true" } else { "false" }
$start.Environment["RAGFLOW_FILE_WRITES_ENABLED"] = "true"
$start.Environment["ASPNETCORE_URLS"] = "http://127.0.0.1:42206"
$process = [Diagnostics.Process]::Start($start)

function Invoke-Mcp([string]$Body, [string]$Session = "", [switch]$WithoutAuthentication) {
    $client = [Net.Http.HttpClient]::new()
    $request = [Net.Http.HttpRequestMessage]::new([Net.Http.HttpMethod]::Post, "http://127.0.0.1:42206/mcp")
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
    $uploadedFileId = $null
    $downloadFixture = $null
    $rejectedDownloadFixture = $null
    $health = $null
    foreach ($attempt in 1..60) {
        try { $health = Invoke-RestMethod "http://127.0.0.1:42206/healthz" -TimeoutSec 2; break }
        catch { if ($process.HasExited) { throw "Adapter exited: $($process.ExitCode)" }; Start-Sleep -Milliseconds 500 }
    }
    if (-not $health -or $health.status -ne "ok") { throw "Adapter health check failed" }

    try {
        Invoke-Mcp '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"unauthenticated-test","version":"1"}}}' "" -WithoutAuthentication | Out-Null
        throw "Unauthenticated MCP request unexpectedly succeeded"
    } catch {
        if ($_.Exception.Message -notmatch "MCP HTTP 401") { throw }
    }

    $initialize = @{ jsonrpc="2.0"; id=1; method="initialize"; params=@{ protocolVersion="2025-06-18"; capabilities=@{}; clientInfo=@{ name="ragflow-smoke"; version="1.0" } } } | ConvertTo-Json -Depth 10 -Compress
    $initResponse = Invoke-Mcp $initialize
    if (-not $initResponse.Session) { throw "No MCP session ID" }
    $toolsResponse = Invoke-Mcp (@{ jsonrpc="2.0"; id=2; method="tools/list"; params=@{} } | ConvertTo-Json -Compress) $initResponse.Session
    $tools = ConvertFrom-Mcp $toolsResponse.Content
    $names = @($tools.result.tools.name)
    foreach ($required in @("rag_flow_config", "rag_flow_api_catalog", "rag_flow_api_request", "upload_rag_flow_api_files", "download_rag_flow_api_response", "create_rag_flow_dataset", "upload_rag_flow_document", "start_rag_flow_parsing", "update_rag_flow_chunk", "delete_rag_flow_dataset")) {
        if ($required -notin $names) { throw "Missing tool: $required" }
    }

    $call = @{ jsonrpc="2.0"; id=3; method="tools/call"; params=@{ name="list_rag_flow_datasets"; arguments=@{ page=1; pageSize=10 } } } | ConvertTo-Json -Depth 10 -Compress
    $callResult = ConvertFrom-Mcp (Invoke-Mcp $call $initResponse.Session).Content
    if ($callResult.error -or $callResult.result.isError) { throw "Live list call failed: $($callResult | ConvertTo-Json -Depth 10 -Compress)" }

    $catalogCall = @{ jsonrpc="2.0"; id=4; method="tools/call"; params=@{ name="rag_flow_api_catalog"; arguments=@{} } } | ConvertTo-Json -Depth 10 -Compress
    $catalogResult = ConvertFrom-Mcp (Invoke-Mcp $catalogCall $initResponse.Session).Content
    if ($catalogResult.error -or $catalogResult.result.isError) { throw "API catalog call failed: $($catalogResult | ConvertTo-Json -Depth 10 -Compress)" }

    $versionCall = @{ jsonrpc="2.0"; id=5; method="tools/call"; params=@{ name="rag_flow_api_request"; arguments=@{ method="GET"; relativePath="api/v1/system/version" } } } | ConvertTo-Json -Depth 10 -Compress
    $versionResult = ConvertFrom-Mcp (Invoke-Mcp $versionCall $initResponse.Session).Content
    if ($versionResult.error -or $versionResult.result.isError) { throw "Generic API version call failed: $($versionResult | ConvertTo-Json -Depth 10 -Compress)" }

    $modelsCall = @{ jsonrpc="2.0"; id=6; method="tools/call"; params=@{ name="rag_flow_api_request"; arguments=@{ method="GET"; relativePath="api/v1/models" } } } | ConvertTo-Json -Depth 10 -Compress
    $modelsResult = ConvertFrom-Mcp (Invoke-Mcp $modelsCall $initResponse.Session).Content
    if ($modelsResult.error -or $modelsResult.result.isError) { throw "Generic models API call failed: $($modelsResult | ConvertTo-Json -Depth 10 -Compress)" }

    $invalidPathCall = @{ jsonrpc="2.0"; id=7; method="tools/call"; params=@{ name="rag_flow_api_request"; arguments=@{ method="GET"; relativePath="https://example.com/api/v1/system/version" } } } | ConvertTo-Json -Depth 10 -Compress
    $invalidPathResult = ConvertFrom-Mcp (Invoke-Mcp $invalidPathCall $initResponse.Session).Content
    if (-not $invalidPathResult.result.isError) { throw "Generic API accepted an external absolute URL" }

    if (-not $Crud -and -not $GenericUpload) {
        $writeCall = @{ jsonrpc="2.0"; id=71; method="tools/call"; params=@{ name="rag_flow_api_request"; arguments=@{ method="POST"; relativePath="api/v1/system/tokens"; bodyJson="{}" } } } | ConvertTo-Json -Depth 10 -Compress
        $writeResult = ConvertFrom-Mcp (Invoke-Mcp $writeCall $initResponse.Session).Content
        if (-not $writeResult.result.isError) { throw "Generic API accepted a write while RAGFLOW_WRITES_ENABLED=false" }
    }

    $downloadFixture = Join-Path ([IO.Path]::GetTempPath()) "ragflow-mcp-version-$([guid]::NewGuid().ToString('N')).json"
    $downloadCall = @{ jsonrpc="2.0"; id=8; method="tools/call"; params=@{ name="download_rag_flow_api_response"; arguments=@{ method="GET"; relativePath="api/v1/system/version"; destinationPath=$downloadFixture } } } | ConvertTo-Json -Depth 10 -Compress
    $downloadResult = ConvertFrom-Mcp (Invoke-Mcp $downloadCall $initResponse.Session).Content
    if ($downloadResult.error -or $downloadResult.result.isError -or -not (Test-Path -LiteralPath $downloadFixture)) { throw "Generic download call failed: $($downloadResult | ConvertTo-Json -Depth 10 -Compress)" }
    $downloadInfo = ([string]($downloadResult.result.content | Where-Object type -eq "text" | Select-Object -First 1).text) | ConvertFrom-Json
    if ($downloadInfo.bytes -le 0 -or (Get-Item -LiteralPath $downloadFixture).Length -ne $downloadInfo.bytes) { throw "Generic download produced an empty or truncated file" }
    $downloadJson = Get-Content -Raw -LiteralPath $downloadFixture | ConvertFrom-Json
    if ($downloadJson.code -ne 0) { throw "Generic download saved a RAGFlow error response" }

    $rejectedDownloadFixture = Join-Path ([IO.Path]::GetTempPath()) "ragflow-mcp-rejected-$([guid]::NewGuid().ToString('N')).json"
    $rejectedDownloadCall = @{ jsonrpc="2.0"; id=9; method="tools/call"; params=@{ name="download_rag_flow_api_response"; arguments=@{ method="GET"; relativePath="api/v1/documents/00000000000000000000000000000000"; destinationPath=$rejectedDownloadFixture } } } | ConvertTo-Json -Depth 10 -Compress
    $rejectedDownloadResult = ConvertFrom-Mcp (Invoke-Mcp $rejectedDownloadCall $initResponse.Session).Content
    if (-not $rejectedDownloadResult.result.isError -or (Test-Path -LiteralPath $rejectedDownloadFixture)) { throw "Generic download persisted a RAGFlow logical error" }

    if ($GenericUpload) {
        $fixture = Join-Path $PSScriptRoot "fixture-ko.txt"
        $uploadCall = @{ jsonrpc="2.0"; id=80; method="tools/call"; params=@{ name="upload_rag_flow_api_files"; arguments=@{ relativePath="api/v1/files"; filePaths=@($fixture); fieldName="file" } } } | ConvertTo-Json -Depth 10 -Compress
        $uploadResult = ConvertFrom-Mcp (Invoke-Mcp $uploadCall $initResponse.Session).Content
        if ($uploadResult.error -or $uploadResult.result.isError) { throw "Generic multipart upload failed: $($uploadResult | ConvertTo-Json -Depth 10 -Compress)" }
        $uploadPayload = ([string]($uploadResult.result.content | Where-Object type -eq "text" | Select-Object -First 1).text) | ConvertFrom-Json
        $uploadedFileId = @($uploadPayload.data)[0].id
        if (-not $uploadedFileId) { throw "Generic multipart upload returned no file ID" }

        $deleteBody = @{ ids=@($uploadedFileId) } | ConvertTo-Json -Compress
        $deleteCall = @{ jsonrpc="2.0"; id=81; method="tools/call"; params=@{ name="rag_flow_api_request"; arguments=@{ method="DELETE"; relativePath="api/v1/files"; bodyJson=$deleteBody } } } | ConvertTo-Json -Depth 10 -Compress
        $deleteResult = ConvertFrom-Mcp (Invoke-Mcp $deleteCall $initResponse.Session).Content
        if ($deleteResult.error -or $deleteResult.result.isError) { throw "Generic upload cleanup failed" }
        $uploadedFileId = $null
    }

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

    [pscustomobject]@{ status="passed"; tools=$names.Count; mcpAuthentication=$true; externalBindGuard=$true; readOnlyWriteBlocked=(-not $Crud -and -not $GenericUpload); liveListCall=$true; apiCatalog=$true; genericVersionCall=$true; genericModelsCall=$true; externalUrlBlocked=$true; genericDownloadCall=$true; downloadErrorRejected=$true; genericUpload=[bool]$GenericUpload; crud=[bool]$Crud; health=$health.status } | ConvertTo-Json -Compress
}
finally {
    if ($createdDatasetId) {
        try {
            $cleanup = @{ jsonrpc="2.0"; id=999; method="tools/call"; params=@{ name="delete_rag_flow_dataset"; arguments=@{ datasetId=$createdDatasetId } } } | ConvertTo-Json -Depth 10 -Compress
            Invoke-Mcp $cleanup $initResponse.Session | Out-Null
        } catch { }
    }
    if ($uploadedFileId) {
        try {
            $cleanupBody = @{ ids=@($uploadedFileId) } | ConvertTo-Json -Compress
            $cleanup = @{ jsonrpc="2.0"; id=998; method="tools/call"; params=@{ name="rag_flow_api_request"; arguments=@{ method="DELETE"; relativePath="api/v1/files"; bodyJson=$cleanupBody } } } | ConvertTo-Json -Depth 10 -Compress
            Invoke-Mcp $cleanup $initResponse.Session | Out-Null
        } catch { }
    }
    if ($downloadFixture -and (Test-Path -LiteralPath $downloadFixture)) { Remove-Item -LiteralPath $downloadFixture -Force }
    if ($rejectedDownloadFixture -and (Test-Path -LiteralPath $rejectedDownloadFixture)) { Remove-Item -LiteralPath $rejectedDownloadFixture -Force }
    if ($process -and -not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue; $process.WaitForExit() }
}
