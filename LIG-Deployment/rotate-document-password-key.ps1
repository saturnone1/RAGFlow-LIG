param(
    [ValidateSet("audit", "rotate")]
    [string]$Action = "audit",
    [string]$NewKeyId = "",
    [string]$ExpectedFingerprint = ""
)

$ErrorActionPreference = "Stop"
$deploymentDirectory = $PSScriptRoot
$secretFile = Join-Path $deploymentDirectory ".env.secret"
$launcher = Join-Path $deploymentDirectory "lig-ragflow.ps1"
$containerName = ""

function Read-EnvValues([string]$Path) {
    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
        $name, $value = $line -split '=', 2
        $values[$name.Trim()] = $value.Trim()
    }
    return $values
}

function Set-EnvValue([string[]]$Lines, [string]$Name, [string]$Value) {
    $replacement = "$Name=$Value"
    for ($index = 0; $index -lt $Lines.Count; $index++) {
        if ($Lines[$index] -match "^\s*$([regex]::Escape($Name))=") {
            $Lines[$index] = $replacement
            return ,$Lines
        }
    }
    return ,@($Lines + $replacement)
}

function Invoke-KeyTool([string[]]$Arguments) {
    if (-not $script:containerName) {
        $previousErrorActionPreference = $ErrorActionPreference
        $dockerExitCode = 1
        try {
            $ErrorActionPreference = "Continue"
            $containerNames = @(& docker ps --format '{{.Names}}' 2>&1 | ForEach-Object { $_.ToString() })
            $dockerExitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        if ($dockerExitCode -ne 0) { throw "Could not query running Docker containers." }
        $script:containerName = $containerNames |
            Where-Object { $_ -in @("lig-ragflow-ragflow-cpu-1", "lig-ragflow-ragflow-gpu-1") } |
            Select-Object -First 1
    }
    if (-not $script:containerName) { throw "No running LIG RAGFlow application container was found." }
    $previousErrorActionPreference = $ErrorActionPreference
    $exitCode = 1
    try {
        # Native tools can write harmless diagnostics to stderr. Preserve the
        # output and decide success from Docker's process exit code.
        $ErrorActionPreference = "Continue"
        $output = @(& docker exec $script:containerName python -m lig_runtime.document_key_rotation @Arguments 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($exitCode -ne 0) { throw "Document key operation failed: $($output -join [Environment]::NewLine)" }
    $jsonLine = @($output | ForEach-Object { $_.ToString() } | Where-Object { $_ -match '^\s*\{' }) |
        Select-Object -Last 1
    if (-not $jsonLine) { throw "Document key operation returned no JSON result." }
    return $jsonLine | ConvertFrom-Json
}

if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) {
    throw "Run .\lig-ragflow.ps1 config before auditing or rotating document keys."
}

if ($Action -eq "audit") {
    $result = Invoke-KeyTool @("--fingerprint")
    $dryRun = Invoke-KeyTool @()
    if ($ExpectedFingerprint -and $result.fingerprint -ne $ExpectedFingerprint) {
        throw "The runtime keyring fingerprint does not match the expected value for this deployment."
    }
    Write-Host "Active document password key: $($result.active_key_id)"
    Write-Host "Configured key ids: $($result.configured_key_ids -join ', ')"
    Write-Host "Keyring fingerprint: $($result.fingerprint)"
    Write-Host "Documents requiring rewrap: $($dryRun.rewrap_candidates)"
    exit 0
}

$values = Read-EnvValues $secretFile
$oldKey = $values["LIG_DOCUMENT_PASSWORD_KEY"]
$oldKeyId = if ($values["LIG_DOCUMENT_PASSWORD_KEY_ID"]) { $values["LIG_DOCUMENT_PASSWORD_KEY_ID"] } else { "primary" }
if ([string]::IsNullOrWhiteSpace($oldKey)) { throw "LIG_DOCUMENT_PASSWORD_KEY is missing." }
if ([string]::IsNullOrWhiteSpace($NewKeyId)) { $NewKeyId = "key-$((Get-Date).ToUniversalTime().ToString('yyyyMMddHHmmss'))" }
if ($NewKeyId -notmatch '^[A-Za-z0-9._-]{1,64}$') { throw "NewKeyId contains unsupported characters." }
if ($NewKeyId -eq $oldKeyId) { throw "NewKeyId must differ from the active key id." }

$keyBytes = New-Object byte[] 32
$generator = [Security.Cryptography.RandomNumberGenerator]::Create()
try { $generator.GetBytes($keyBytes) } finally { $generator.Dispose() }
$newKey = [Convert]::ToBase64String($keyBytes)
$previous = $values["LIG_DOCUMENT_PASSWORD_PREVIOUS_KEYS"]
$oldEntry = "${oldKeyId}:$oldKey"
if ([string]::IsNullOrWhiteSpace($previous)) { $previous = $oldEntry }
elseif (($previous -split ',') -notcontains $oldEntry) { $previous = "$previous,$oldEntry" }
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddHHmmss")
$backupFile = "$secretFile.$timestamp.bak"
Copy-Item -LiteralPath $secretFile -Destination $backupFile
$lines = @(Get-Content -LiteralPath $secretFile)
$lines = Set-EnvValue $lines "LIG_DOCUMENT_PASSWORD_KEY" $newKey
$lines = Set-EnvValue $lines "LIG_DOCUMENT_PASSWORD_KEY_ID" $NewKeyId
$lines = Set-EnvValue $lines "LIG_DOCUMENT_PASSWORD_PREVIOUS_KEYS" $previous
[IO.File]::WriteAllLines($secretFile, $lines, [Text.UTF8Encoding]::new($false))

$rewrapStarted = $false
try {
    & $launcher start
    if ($LASTEXITCODE -ne 0) { throw "RAGFlow restart failed after key configuration update." }
    $rewrapStarted = $true
    $result = Invoke-KeyTool @("--apply")
    Write-Host "Document password key rotation completed. Rewrapped documents: $($result.rewrapped)"
    Write-Host "Backup containing the prior key configuration: $backupFile"
    Write-Host "Keep the previous key configured until every RAGFlow node reports the same keyring fingerprint."
}
catch {
    if (-not $rewrapStarted) {
        Copy-Item -LiteralPath $backupFile -Destination $secretFile -Force
        & $launcher start
    }
    else {
        # Rewrap is committed in batches. Some records may already reference
        # the new key, so keep both the new active and old previous key and let
        # the operator fix the cause, audit, and rerun rotate/apply safely.
        Write-Warning "Key rewrap did not finish. The dual-key configuration was retained to keep both old and already-rewrapped records readable. Run audit before retrying."
    }
    throw
}
