param(
    [Parameter(Mandatory = $true)]
    [string]$EncryptedXlsx,
    [Parameter(Mandatory = $true)]
    [string]$EncryptedPptx,
    [Parameter(Mandatory = $true)]
    [string]$Password,
    [string]$BaseUrl = "http://127.0.0.1:42301/api/v1",
    [string]$ApiKey = $env:RAGFLOW_API_KEY,
    [int]$TimeoutSeconds = 600
)

$ErrorActionPreference = "Stop"
$datasetIds = [Collections.Generic.List[string]]::new()
$concurrentFiles = [Collections.Generic.List[string]]::new()

function Assert-Result($Result, [string]$Operation) {
    if ($null -eq $Result -or $Result.code -ne 0) {
        throw "$Operation failed: $($Result.message)"
    }
}

function Invoke-JsonApi([string]$Method, [string]$Path, $Body = $null) {
    $arguments = @{
        Uri = "$BaseUrl$Path"
        Method = $Method
        Headers = $script:headers
        TimeoutSec = 60
    }
    if ($null -ne $Body) {
        $arguments.ContentType = "application/json"
        $arguments.Body = $Body | ConvertTo-Json -Depth 10 -Compress
    }
    return Invoke-RestMethod @arguments
}

function New-TestDataset([string]$ChunkMethod) {
    $name = "codex-document-e2e-$ChunkMethod-$([guid]::NewGuid().ToString('N').Substring(0, 10))"
    $result = Invoke-JsonApi "Post" "/datasets" @{ name = $name; chunk_method = $ChunkMethod }
    Assert-Result $result "create $ChunkMethod dataset"
    $script:datasetIds.Add($result.data.id)
    return $result.data.id
}

function Send-Document([string]$DatasetId, [string]$Path, [string]$DocumentPassword) {
    $form = @{
        file = Get-Item -LiteralPath $Path
        document_passwords = (ConvertTo-Json @($DocumentPassword) -Compress)
    }
    return Invoke-RestMethod -Uri "$BaseUrl/datasets/$DatasetId/documents" -Method Post -Headers $script:headers -Form $form -TimeoutSec 120
}

if ([string]::IsNullOrWhiteSpace($ApiKey) -or $ApiKey -match '^replace-') {
    throw "ApiKey or RAGFLOW_API_KEY must contain the test user's personal RAGFlow API key."
}
$headers = @{ Authorization = "Bearer $ApiKey" }

try {
    $tableDataset = New-TestDataset "table"
    $paperDataset = New-TestDataset "paper"

    $wrongPassword = Send-Document $tableDataset $EncryptedXlsx "incorrect-password"
    if ($wrongPassword.code -eq 0 -or $wrongPassword.message -notmatch "incorrect|unsupported") {
        throw "Wrong Office password was not rejected with an actionable error."
    }

    $incompatible = Send-Document $paperDataset $EncryptedXlsx $Password
    if ($incompatible.code -eq 0 -or $incompatible.message -notmatch "cannot be chunked") {
        throw "The extension/chunker preflight did not reject XLSX with the paper method."
    }

    $xlsxUpload = Send-Document $tableDataset $EncryptedXlsx $Password
    Assert-Result $xlsxUpload "encrypted XLSX upload"
    $pptxUpload = Send-Document $tableDataset $EncryptedPptx $Password
    Assert-Result $pptxUpload "encrypted PPTX upload"
    $primaryDocuments = @($xlsxUpload.data[0], $pptxUpload.data[0])

    $jobs = 1..3 | ForEach-Object {
        $copyPath = Join-Path ([IO.Path]::GetTempPath()) "rag-lig-e2e-$([guid]::NewGuid().ToString('N')).xlsx"
        Copy-Item -LiteralPath $EncryptedXlsx -Destination $copyPath
        $concurrentFiles.Add($copyPath)
        Start-Job -ScriptBlock {
            param($Url, $DatasetId, $FilePath, $DocumentPassword, $Authorization)
            $form = @{
                file = Get-Item -LiteralPath $FilePath
                document_passwords = (ConvertTo-Json @($DocumentPassword) -Compress)
            }
            Invoke-RestMethod -Uri "$Url/datasets/$DatasetId/documents" -Method Post `
                -Headers @{ Authorization = $Authorization } -Form $form -TimeoutSec 120
        } -ArgumentList $BaseUrl, $tableDataset, $copyPath, $Password, $headers.Authorization
    }
    $concurrentResults = @($jobs | Receive-Job -Wait -AutoRemoveJob)
    if ($concurrentResults.Count -ne 3 -or @($concurrentResults | Where-Object code -ne 0).Count -ne 0) {
        throw "Concurrent encrypted Office uploads did not all succeed."
    }

    $ingest = Invoke-JsonApi "Post" "/documents/ingest" @{
        doc_ids = @($primaryDocuments | ForEach-Object id)
        run = 1
        delete = $true
    }
    Assert-Result $ingest "start encrypted Office parsing"

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        Start-Sleep -Seconds 3
        $list = Invoke-JsonApi "Get" "/datasets/$tableDataset/documents?page=1&page_size=100"
        Assert-Result $list "list parsed documents"
        $states = @($primaryDocuments | ForEach-Object {
            $id = $_.id
            $list.data.docs | Where-Object id -eq $id | Select-Object -First 1
        })
        if (@($states | Where-Object { $_.run -in @("4", "FAIL") }).Count -gt 0) {
            $failure = $states | Where-Object { $_.run -in @("4", "FAIL") } | Select-Object -First 1
            throw "Document parsing failed: $($failure.name): $($failure.progress_msg)"
        }
        $complete = $states.Count -eq 2 -and @($states | Where-Object { $_.run -in @("3", "DONE") }).Count -eq 2
    } while (-not $complete -and (Get-Date) -lt $deadline)

    if (-not $complete) { throw "Encrypted Office parsing did not finish within $TimeoutSeconds seconds." }
    if (@($states | Where-Object { $_.chunk_count -lt 1 }).Count -gt 0) {
        throw "A parsed Office document produced no chunks."
    }

    [pscustomobject]@{
        Status = "passed"
        Parsed = @($states | ForEach-Object { "{0}:{1}" -f $_.name, $_.chunk_count })
        ConcurrentUploads = $concurrentResults.Count
        WrongPasswordRejected = $true
        IncompatibleChunkerRejected = $true
    } | ConvertTo-Json -Depth 3
}
finally {
    if ($datasetIds.Count -gt 0) {
        try {
            $cleanup = Invoke-JsonApi "Delete" "/datasets" @{ ids = @($datasetIds) }
            Assert-Result $cleanup "remove E2E datasets"
        }
        catch {
            Write-Warning "E2E dataset cleanup failed: $_"
        }
    }
    foreach ($temporaryFile in $concurrentFiles) {
        Remove-Item -LiteralPath $temporaryFile -Force -ErrorAction SilentlyContinue
    }
}
