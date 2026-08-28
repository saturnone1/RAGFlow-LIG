param(
    [ValidateSet("config", "pull", "build", "gpu-build", "ui-build", "mcp-build", "ocr-build", "paddleocr-start", "paddleocr-stop", "paddleocr-status", "paddleocr-test", "paddleocr-vl-build", "paddleocr-vl-pull", "paddleocr-vl-start", "paddleocr-vl-stop", "paddleocr-vl-status", "paddleocr-vl-test", "embedding-build", "embedding-start", "embedding-stop", "embedding-status", "embedding-test", "start", "stop", "status", "diagnostics", "recovery-test", "logs")]
    [string]$Action = "status"
)

$ErrorActionPreference = "Stop"
$deploymentDirectory = $PSScriptRoot
$workspaceDirectory = Split-Path $deploymentDirectory -Parent
$dockerDirectory = Join-Path $workspaceDirectory "RAGFlow\docker"
$upstreamEnvFile = Join-Path $dockerDirectory ".env"
$ligEnvFile = Join-Path $deploymentDirectory ".env.lig"
$secretFile = Join-Path $deploymentDirectory ".env.secret"
$persistentStateDirectory = Join-Path ([Environment]::GetFolderPath("LocalApplicationData")) "LIG-RAGFlow"
$persistentSecretFile = Join-Path $persistentStateDirectory ".env.secret"
$logDirectory = Join-Path $deploymentDirectory "ragflow-logs"
$mcpDataDirectory = Join-Path $deploymentDirectory "mcp-files"
$uiDockerfile = Join-Path $workspaceDirectory "LIG-UI\Dockerfile"
$gpuUiDockerfile = Join-Path $workspaceDirectory "LIG-UI\Dockerfile.gpu"
$mcpDirectory = Join-Path $workspaceDirectory "RAGFlow-MCP-LIG"
$mcpDockerfile = Join-Path $mcpDirectory "Dockerfile"
$ocrDirectory = Join-Path $workspaceDirectory "LIG-PaddleOCR"
$ocrDockerfile = Join-Path $ocrDirectory "Dockerfile"
$ocrVlDirectory = Join-Path $workspaceDirectory "LIG-PaddleOCR-VL"
$ocrVlDockerfile = Join-Path $ocrVlDirectory "Dockerfile"
$ocrVlPipelineCpuDockerfile = Join-Path $ocrVlDirectory "Dockerfile.pipeline-cpu"
$ocrVlVlmDockerfile = Join-Path $ocrVlDirectory "Dockerfile.vlm"
$embeddingDirectory = Join-Path $workspaceDirectory "LIG-Embedding"
$embeddingModelDockerfile = Join-Path $embeddingDirectory "Dockerfile.model"
$embeddingAdapterDockerfile = Join-Path $embeddingDirectory "Dockerfile.adapter"

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
$composeArguments += @("--env-file", $secretFile)
$composeArguments += @(
    "-f", (Join-Path $dockerDirectory "docker-compose.yml"),
    "-f", (Join-Path $deploymentDirectory "docker-compose.lig.yml")
)
$allServiceProfileArguments = @(
    "--profile", "infinity",
    "--profile", "cpu",
    "--profile", "gpu",
    "--profile", "deepdoc",
    "--profile", "paddleocr",
    "--profile", "paddleocr-vl",
    "--profile", "embedding-cpu"
)

function Invoke-Compose([string[]]$Arguments) {
    Ensure-LigSecrets
    $dockerExecutable = (Get-Command docker -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    $previousErrorActionPreference = $ErrorActionPreference
    $dockerExitCode = 1
    try {
        # Windows PowerShell 5.1 turns redirected native stderr into
        # NativeCommandError records. Compose writes progress to stderr even
        # when it succeeds, so keep the text visible and trust its exit code.
        $ErrorActionPreference = "Continue"
        & $dockerExecutable @composeArguments @Arguments 2>&1 | ForEach-Object { Write-Host $_ }
        $dockerExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($dockerExitCode -ne 0) {
        throw "docker compose failed with exit code $dockerExitCode"
    }
}

function Invoke-Docker([string[]]$Arguments) {
    $dockerExecutable = (Get-Command docker -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    $previousErrorActionPreference = $ErrorActionPreference
    $dockerExitCode = 1
    try {
        $ErrorActionPreference = "Continue"
        & $dockerExecutable @Arguments 2>&1 | ForEach-Object { Write-Host $_ }
        $dockerExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($dockerExitCode -ne 0) { throw "docker failed with exit code $dockerExitCode" }
}

function Invoke-DockerCapture([string[]]$Arguments, [switch]$AllowFailure) {
    $dockerExecutable = (Get-Command docker -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    $previousErrorActionPreference = $ErrorActionPreference
    $dockerExitCode = 1
    $output = @()
    try {
        $ErrorActionPreference = "Continue"
        $output = @(& $dockerExecutable @Arguments 2>&1 | ForEach-Object { $_.ToString() })
        $dockerExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($dockerExitCode -ne 0 -and -not $AllowFailure) {
        throw "docker failed with exit code $dockerExitCode"
    }
    return [pscustomobject]@{
        ExitCode = $dockerExitCode
        Lines = $output
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

function New-RandomSecret {
    $bytes = New-Object byte[] 32
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) }
    finally { $generator.Dispose() }
    return [Convert]::ToBase64String($bytes)
}

function Get-ExistingContainerEnvValue([string]$Name) {
    $containers = Invoke-DockerCapture -Arguments @(
        "ps", "-a", "--filter", "label=com.docker.compose.project=lig-ragflow", "--format", "{{.Names}}"
    ) -AllowFailure
    if ($containers.ExitCode -ne 0) { return $null }
    $orderedNames = @($containers.Lines | Where-Object { $_ -match 'ragflow-(worker-)?(cpu|gpu)' }) + @($containers.Lines)
    foreach ($containerName in $orderedNames | Select-Object -Unique) {
        $environment = Invoke-DockerCapture -Arguments @(
            "inspect", "--format", "{{range .Config.Env}}{{println .}}{{end}}", $containerName
        ) -AllowFailure
        if ($environment.ExitCode -ne 0) { continue }
        $prefix = "$Name="
        $entry = $environment.Lines | Where-Object { $_.StartsWith($prefix, [StringComparison]::Ordinal) } | Select-Object -First 1
        if ($entry) { return $entry.Substring($prefix.Length) }
    }
    return $null
}

function Ensure-LigSecrets {
    if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) {
        if (Test-Path -LiteralPath $persistentSecretFile -PathType Leaf) {
            Copy-Item -LiteralPath $persistentSecretFile -Destination $secretFile
        }
        else {
            Copy-Item -LiteralPath (Join-Path $deploymentDirectory ".env.secret.example") -Destination $secretFile
        }
    }
    elseif (Test-Path -LiteralPath $persistentSecretFile -PathType Leaf) {
        $localValues = Get-EnvFileValues $secretFile
        $localKey = $localValues["LIG_DOCUMENT_PASSWORD_KEY"]
        if ([string]::IsNullOrWhiteSpace($localKey) -or $localKey -eq "generate-a-base64-encoded-32-byte-key") {
            Copy-Item -LiteralPath $persistentSecretFile -Destination $secretFile -Force
        }
    }
    $lines = @(Get-Content -LiteralPath $secretFile)
    $mcpKeyLineIndex = -1
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match '^\s*RAGFLOW_MCP_API_KEY=') { $mcpKeyLineIndex = $index }
    }
    $mcpKey = if ($mcpKeyLineIndex -ge 0) { ($lines[$mcpKeyLineIndex] -split '=', 2)[1].Trim() } else { "" }
    if ([string]::IsNullOrWhiteSpace($mcpKey) -or $mcpKey -eq "ragflow-replace-with-a-local-api-key") {
        $existingMcpKey = Get-ExistingContainerEnvValue "RAGFLOW_MCP_HOST_API_KEY"
        if ($existingMcpKey -and $existingMcpKey -ne "ragflow-replace-with-a-local-api-key") {
            $mcpKey = $existingMcpKey
            Write-Host "Recovered the existing server-side official MCP API key from the LIG runtime."
        }
        else {
            $mcpKey = "ragflow-$((New-RandomSecret).TrimEnd('=').Replace('+', '-').Replace('/', '_'))"
            Write-Host "Generated the server-side official MCP API key. MCP clients do not need this key."
        }
        $mcpKeyLine = "RAGFLOW_MCP_API_KEY=$mcpKey"
        if ($mcpKeyLineIndex -ge 0) { $lines[$mcpKeyLineIndex] = $mcpKeyLine } else { $lines += $mcpKeyLine }
    }
    $keyLineIndex = -1
    $legacyKeyLineIndex = -1
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match '^\s*LIG_DOCUMENT_PASSWORD_KEY=') { $keyLineIndex = $index }
        if ($lines[$index] -match '^\s*LIG_PDF_PASSWORD_KEY=') { $legacyKeyLineIndex = $index }
    }
    $currentValue = if ($keyLineIndex -ge 0) { ($lines[$keyLineIndex] -split '=', 2)[1].Trim() } else { "" }
    if (([string]::IsNullOrWhiteSpace($currentValue) -or $currentValue -eq "generate-a-base64-encoded-32-byte-key") -and $legacyKeyLineIndex -ge 0) {
        $legacyValue = ($lines[$legacyKeyLineIndex] -split '=', 2)[1].Trim()
        if (-not [string]::IsNullOrWhiteSpace($legacyValue) -and $legacyValue -ne "generate-a-base64-encoded-32-byte-key") {
            if ($keyLineIndex -ge 0) { $lines[$keyLineIndex] = "LIG_DOCUMENT_PASSWORD_KEY=$legacyValue" }
            else { $lines[$legacyKeyLineIndex] = "LIG_DOCUMENT_PASSWORD_KEY=$legacyValue"; $keyLineIndex = $legacyKeyLineIndex; $legacyKeyLineIndex = -1 }
            $currentValue = $legacyValue
            Write-Host "Migrated the existing document password encryption key name."
        }
    }
    if ([string]::IsNullOrWhiteSpace($currentValue) -or $currentValue -eq "generate-a-base64-encoded-32-byte-key") {
        $existingKey = Get-ExistingContainerEnvValue "LIG_DOCUMENT_PASSWORD_KEY"
        if ($existingKey) {
            if ($keyLineIndex -ge 0) { $lines[$keyLineIndex] = "LIG_DOCUMENT_PASSWORD_KEY=$existingKey" }
            else { $lines += "LIG_DOCUMENT_PASSWORD_KEY=$existingKey"; $keyLineIndex = $lines.Count - 1 }
            $currentValue = $existingKey
            Write-Host "Recovered the existing document password key from the LIG runtime."
        }
    }
    if ([string]::IsNullOrWhiteSpace($currentValue) -or $currentValue -eq "generate-a-base64-encoded-32-byte-key") {
        $keyLine = "LIG_DOCUMENT_PASSWORD_KEY=$(New-RandomSecret)"
        if ($keyLineIndex -ge 0) { $lines[$keyLineIndex] = $keyLine } else { $lines += $keyLine }
        Write-Host "Generated the local document password encryption key in LIG-Deployment\.env.secret."
    }
    if ($legacyKeyLineIndex -ge 0) { $lines = @($lines | Where-Object { $_ -notmatch '^\s*LIG_PDF_PASSWORD_KEY=' }) }
    if (-not ($lines | Where-Object { $_ -match '^\s*LIG_DOCUMENT_PASSWORD_KEY_ID=' })) {
        $existingKeyId = Get-ExistingContainerEnvValue "LIG_DOCUMENT_PASSWORD_KEY_ID"
        $lines += "LIG_DOCUMENT_PASSWORD_KEY_ID=$(if ($existingKeyId) { $existingKeyId } else { 'primary' })"
    }
    if (-not ($lines | Where-Object { $_ -match '^\s*LIG_DOCUMENT_PASSWORD_PREVIOUS_KEYS=' })) {
        $existingPreviousKeys = Get-ExistingContainerEnvValue "LIG_DOCUMENT_PASSWORD_PREVIOUS_KEYS"
        $lines += "LIG_DOCUMENT_PASSWORD_PREVIOUS_KEYS=$existingPreviousKeys"
    }
    $ocrTokenLineIndex = -1
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match '^\s*PADDLEOCR_INTERNAL_TOKEN=') { $ocrTokenLineIndex = $index }
    }
    $ocrToken = if ($ocrTokenLineIndex -ge 0) { ($lines[$ocrTokenLineIndex] -split '=', 2)[1].Trim() } else { "" }
    if ([string]::IsNullOrWhiteSpace($ocrToken) -or $ocrToken -eq "replace-with-a-random-internal-token") {
        $existingOcrToken = Get-ExistingContainerEnvValue "PADDLEOCR_INTERNAL_TOKEN"
        if ($existingOcrToken) {
            $ocrTokenLine = "PADDLEOCR_INTERNAL_TOKEN=$existingOcrToken"
            if ($ocrTokenLineIndex -ge 0) { $lines[$ocrTokenLineIndex] = $ocrTokenLine } else { $lines += $ocrTokenLine; $ocrTokenLineIndex = $lines.Count - 1 }
            $ocrToken = $existingOcrToken
            Write-Host "Recovered the existing internal PaddleOCR token from the LIG runtime."
        }
    }
    if ([string]::IsNullOrWhiteSpace($ocrToken) -or $ocrToken -eq "replace-with-a-random-internal-token") {
        $ocrTokenLine = "PADDLEOCR_INTERNAL_TOKEN=$(New-RandomSecret)"
        if ($ocrTokenLineIndex -ge 0) { $lines[$ocrTokenLineIndex] = $ocrTokenLine } else { $lines += $ocrTokenLine }
        $ocrToken = ($ocrTokenLine -split '=', 2)[1]
        Write-Host "Generated the internal PaddleOCR bearer token in LIG-Deployment\.env.secret."
    }
    $ocrVlTokenLineIndex = -1
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match '^\s*PADDLEOCR_VL_INTERNAL_TOKEN=') { $ocrVlTokenLineIndex = $index }
    }
    $ocrVlToken = if ($ocrVlTokenLineIndex -ge 0) { ($lines[$ocrVlTokenLineIndex] -split '=', 2)[1].Trim() } else { "" }
    if (
        [string]::IsNullOrWhiteSpace($ocrVlToken) -or
        $ocrVlToken -eq "replace-with-a-separate-random-internal-token" -or
        $ocrVlToken -eq $ocrToken
    ) {
        $existingOcrVlToken = Get-ExistingContainerEnvValue "PADDLEOCR_VL_ACCESS_TOKEN"
        if ($existingOcrVlToken -and $existingOcrVlToken -ne $ocrToken) {
            $ocrVlToken = $existingOcrVlToken
            Write-Host "Recovered the existing internal PaddleOCR-VL token from the LIG runtime."
        }
        else {
            $ocrVlToken = New-RandomSecret
            Write-Host "Generated a separate internal PaddleOCR-VL bearer token."
        }
        $ocrVlTokenLine = "PADDLEOCR_VL_INTERNAL_TOKEN=$ocrVlToken"
        if ($ocrVlTokenLineIndex -ge 0) { $lines[$ocrVlTokenLineIndex] = $ocrVlTokenLine } else { $lines += $ocrVlTokenLine }
    }
    [IO.File]::WriteAllLines($secretFile, $lines, [Text.UTF8Encoding]::new($false))
    if (-not (Test-Path -LiteralPath $persistentStateDirectory -PathType Container)) {
        New-Item -ItemType Directory -Path $persistentStateDirectory -Force | Out-Null
    }
    Copy-Item -LiteralPath $secretFile -Destination $persistentSecretFile -Force
}

function Assert-LigConfiguration {
    Ensure-LigSecrets
    $configuration = Get-EnvFileValues $ligEnvFile
    $workerValue = Get-ConfigurationValue $configuration "TASK_EXECUTOR_WORKERS" "3"
    $workers = 0
    if (-not [int]::TryParse($workerValue, [ref]$workers) -or $workers -lt 1) {
        throw "TASK_EXECUTOR_WORKERS must be a positive integer. Current value: $workerValue"
    }
    foreach ($settingName in @("DOC_BULK_SIZE", "EMBEDDING_BATCH_SIZE", "THREAD_POOL_MAX_WORKERS", "PADDLEOCR_JOB_WORKERS", "PADDLEOCR_VL_JOB_WORKERS", "PDF_TASK_PAGE_SIZE", "PADDLEOCR_TASK_PAGE_SIZE", "PADDLEOCR_MAX_PENDING_JOBS", "PADDLEOCR_VL_MAX_PENDING_JOBS", "PADDLEOCR_MIN_FREE_BYTES", "PADDLEOCR_MAX_PAGE_PIXELS", "PADDLEOCR_DIRECT_WORKERS", "PADDLEOCR_DIRECT_RENDER_DPI", "MAX_CONCURRENT_TASKS", "MAX_CONCURRENT_CHUNK_BUILDERS", "TASK_LEASE_SECONDS", "TASK_CANCEL_GRACE_SECONDS", "TASK_CANCEL_POLL_SECONDS", "TASK_PENDING_CLAIM_IDLE_SECONDS", "LIG_INGESTION_MEMORY_RESERVE_BYTES", "LIG_PDF_ESTIMATED_WORKING_BYTES_PER_PAGE", "PADDLEOCR_ESTIMATED_BYTES_PER_PIXEL", "PADDLEOCR_VL_REQUEST_TIMEOUT_SECONDS", "PADDLEOCR_VL_MAX_MODEL_LEN", "PADDLEOCR_VL_MAX_NUM_BATCHED_TOKENS", "PADDLEOCR_VL_MAX_NUM_SEQS", "PADDLEOCR_VL_API_SERVER_COUNT")) {
        $settingValue = Get-ConfigurationValue $configuration $settingName
        if ([string]::IsNullOrWhiteSpace($settingValue)) { continue }
        [long]$parsed = 0
        if (-not [long]::TryParse($settingValue, [ref]$parsed) -or $parsed -lt 1) {
            throw "$settingName must be a positive integer. Current value: $settingValue"
        }
    }
    foreach ($settingName in @("MAX_CONTENT_LENGTH", "QUART_BODY_TIMEOUT", "LIG_DOCUMENT_MAX_BYTES", "PADDLEOCR_MAX_UPLOAD_BYTES", "PADDLEOCR_MAX_PDF_PAGES", "TASK_MAX_CRASH_RETRIES")) {
        $settingValue = Get-ConfigurationValue $configuration $settingName
        if ([string]::IsNullOrWhiteSpace($settingValue)) { continue }
        [long]$parsed = 0
        if (-not [long]::TryParse($settingValue, [ref]$parsed) -or $parsed -lt 0) {
            throw "$settingName must be zero (unlimited) or a positive integer. Current value: $settingValue"
        }
    }
    $memoryPercentValue = Get-ConfigurationValue $configuration "LIG_INGESTION_MEMORY_PERCENT" "25"
    [int]$memoryPercent = 0
    if (-not [int]::TryParse($memoryPercentValue, [ref]$memoryPercent) -or $memoryPercent -lt 1 -or $memoryPercent -gt 100) {
        throw "LIG_INGESTION_MEMORY_PERCENT must be an integer from 1 through 100. Current value: $memoryPercentValue"
    }
    $gpuUtilizationValue = Get-ConfigurationValue $configuration "PADDLEOCR_VL_GPU_MEMORY_UTILIZATION" "0.60"
    [double]$gpuUtilization = 0
    if (-not [double]::TryParse($gpuUtilizationValue, [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$gpuUtilization) -or $gpuUtilization -le 0 -or $gpuUtilization -ge 1) {
        throw "PADDLEOCR_VL_GPU_MEMORY_UTILIZATION must be greater than 0 and less than 1. Current value: $gpuUtilizationValue"
    }
    [long]$maxModelLength = Get-ConfigurationValue $configuration "PADDLEOCR_VL_MAX_MODEL_LEN" "16384"
    [long]$maxBatchedTokens = Get-ConfigurationValue $configuration "PADDLEOCR_VL_MAX_NUM_BATCHED_TOKENS" "16384"
    if ($maxBatchedTokens -lt $maxModelLength) {
        throw "PADDLEOCR_VL_MAX_NUM_BATCHED_TOKENS must be at least PADDLEOCR_VL_MAX_MODEL_LEN."
    }
    $pipelineDevice = Get-ConfigurationValue $configuration "PADDLEOCR_VL_PIPELINE_DEVICE" "cpu"
    if ($pipelineDevice -ne "cpu") {
        throw "PADDLEOCR_VL_PIPELINE_DEVICE는 VRAM 충돌 방지를 위해 cpu여야 합니다. 현재 값: $pipelineDevice"
    }
    $adaptivePageSizing = Get-ConfigurationValue $configuration "ADAPTIVE_PDF_TASK_PAGE_SIZE" "false"
    if ($adaptivePageSizing -notmatch '^(?i:true|false|1|0|yes|no|on|off)$') {
        throw "ADAPTIVE_PDF_TASK_PAGE_SIZE must be true or false. Current value: $adaptivePageSizing"
    }
}

function Invoke-ComposeCapture([string[]]$Arguments, [switch]$AllowFailure) {
    Ensure-LigSecrets
    $result = Invoke-DockerCapture -Arguments ($composeArguments + $Arguments) -AllowFailure:$AllowFailure
    return $result
}

function Test-ComposeGpuReservation($Service) {
    if ($Service -and $Service.gpus) { return $true }
    if (-not $Service -or -not $Service.deploy -or -not $Service.deploy.resources -or -not $Service.deploy.resources.reservations) {
        return $false
    }
    foreach ($device in @($Service.deploy.resources.reservations.devices)) {
        if (@($device.capabilities) -contains "gpu") { return $true }
    }
    return $false
}

function Assert-OcrDeviceTopology {
    $rendered = Invoke-ComposeCapture -Arguments @(
        "--profile", "infinity", "--profile", "cpu", "--profile", "gpu", "--profile", "paddleocr", "--profile", "paddleocr-vl",
        "config", "--format", "json"
    )
    $compose = ($rendered.Lines -join "`n") | ConvertFrom-Json
    $serviceNames = @($compose.services.PSObject.Properties.Name)
    foreach ($required in @("paddleocr-cpu", "paddleocr-vl", "paddleocr-vl-api", "paddleocr-vl-vlm")) {
        if ($required -notin $serviceNames) { throw "Compose에 필수 OCR 서비스가 없습니다: $required" }
    }
    if ($compose.services.'paddleocr-cpu'.environment.PADDLEOCR_DEVICE -ne "cpu") {
        throw "CPU 프로필의 일반 PaddleOCR 장치가 cpu가 아닙니다."
    }
    if (Test-ComposeGpuReservation $compose.services.'paddleocr-cpu') {
        throw "CPU 프로필의 일반 PaddleOCR가 GPU를 요청하고 있습니다."
    }
    if ($compose.services.'paddleocr-vl-api'.environment.PADDLEOCR_VL_PIPELINE_DEVICE -ne "cpu") {
        throw "PaddleOCR-VL 레이아웃 파이프라인은 CPU로 고정되어야 합니다."
    }
    if (Test-ComposeGpuReservation $compose.services.'paddleocr-vl-api') {
        throw "PaddleOCR-VL 레이아웃 파이프라인이 GPU를 요청하고 있습니다."
    }
    if (-not (Test-ComposeGpuReservation $compose.services.'paddleocr-vl-vlm')) {
        throw "PaddleOCR-VL VLM에 GPU 예약이 없습니다."
    }
    $infinity = $compose.services.infinity
    if ($infinity.mem_limit -or $infinity.mem_reservation -or $infinity.cpus -or $infinity.deploy.resources.limits) {
        throw "Infinity에 CPU 또는 메모리 상한이 남아 있습니다. 데이터 손상 방지를 위해 상한 없이 실행해야 합니다."
    }
    foreach ($serviceName in @("ragflow-cpu", "ragflow-gpu", "ragflow-worker-cpu", "ragflow-worker-gpu")) {
        $entrypoint = @($compose.services.$serviceName.entrypoint)
        if (($entrypoint -join " ") -ne "/ragflow/.venv/bin/python -m lig_runtime.container_entrypoint") {
            throw "$serviceName 서비스가 Bash 없는 LIG 실행기를 사용하지 않습니다."
        }
    }
    Write-Host "OCR/Infinity 구성 검증 통과: PP-OCRv5=CPU, VL 레이아웃=CPU, VL VLM=GPU, Infinity=무상한"
}

function Get-ComposeServiceContainerId([string]$Service) {
    $result = Invoke-DockerCapture -Arguments @(
        "ps", "-a",
        "--filter", "label=com.docker.compose.project=lig-ragflow",
        "--filter", "label=com.docker.compose.service=$Service",
        "--format", "{{.ID}}"
    ) -AllowFailure
    if ($result.ExitCode -ne 0) { return $null }
    return $result.Lines | Where-Object { $_ -match '^[0-9a-fA-F]{12,64}$' } | Select-Object -First 1
}

function Show-PaddleOcrVlGpuSummary([string]$ContainerId) {
    if (-not $ContainerId) {
        Write-Warning "PaddleOCR-VL VLM 컨테이너가 없습니다."
        return
    }
    $gpu = Invoke-DockerCapture -Arguments @(
        "exec", $ContainerId, "nvidia-smi",
        "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu",
        "--format=csv,noheader,nounits"
    ) -AllowFailure
    if ($gpu.ExitCode -ne 0) {
        Write-Warning "VLM 컨테이너에서 NVIDIA GPU 상태를 읽지 못했습니다."
        return
    }
    Write-Host ""
    Write-Host "PaddleOCR-VL GPU 상태 (MiB, %):"
    Write-Host "GPU, 전체 VRAM, 사용 VRAM, 여유 VRAM, 사용률"
    $gpu.Lines | ForEach-Object { Write-Host $_ }
}

function Protect-DiagnosticText([string]$Text) {
    if (-not $Text) { return $Text }
    $protected = $Text -replace 'nvapi-[A-Za-z0-9_-]+', '<redacted-nvidia-key>'
    $protected = $protected -replace '(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+', '${1}<redacted>'
    $protected = $protected -replace '(?i)(api[_-]?key\s*["''=:]+\s*)[^\s,"'']+', '${1}<redacted>'
    return $protected
}

function Test-McpInitialize([string]$Url, [string]$BearerToken = "") {
    $headers = @{ Accept = "application/json, text/event-stream" }
    if ($BearerToken) { $headers["Authorization"] = "Bearer $BearerToken" }
    $body = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"lig-diagnostics","version":"1"}}}'
    try {
        $response = Invoke-WebRequest -Uri $Url -Method Post -Headers $headers -ContentType "application/json" -Body $body -UseBasicParsing -TimeoutSec 10
        return [pscustomobject]@{
            Reachable = $true
            StatusCode = [int]$response.StatusCode
            SessionCreated = [bool]$response.Headers["Mcp-Session-Id"]
            Error = $null
        }
    }
    catch {
        $statusCode = $null
        if ($_.Exception.Response) { $statusCode = [int]$_.Exception.Response.StatusCode }
        return [pscustomobject]@{
            Reachable = $false
            StatusCode = $statusCode
            SessionCreated = $false
            Error = Protect-DiagnosticText $_.Exception.Message
        }
    }
}

function Get-RedisQueueDiagnostics([string]$ContainerId, [string]$Password) {
    if (-not $ContainerId -or -not $Password) { return @() }
    $rows = @()
    foreach ($stream in @("te.1.common", "te.0.common")) {
        $lengthResult = Invoke-DockerCapture -Arguments @(
            "exec", $ContainerId, "redis-cli", "--no-auth-warning", "-a", $Password,
            "--raw", "XLEN", $stream
        ) -AllowFailure
        $groupResult = Invoke-DockerCapture -Arguments @(
            "exec", $ContainerId, "redis-cli", "--no-auth-warning", "-a", $Password,
            "--raw", "XINFO", "GROUPS", $stream
        ) -AllowFailure
        $tokens = @($groupResult.Lines)
        $pendingIndex = [Array]::IndexOf($tokens, "pending")
        $lagIndex = [Array]::IndexOf($tokens, "lag")
        $consumersIndex = [Array]::IndexOf($tokens, "consumers")
        $rows += [pscustomobject]@{
            Stream = $stream
            Length = if ($lengthResult.ExitCode -eq 0 -and $lengthResult.Lines.Count) { [long]$lengthResult.Lines[-1] } else { $null }
            Pending = if ($pendingIndex -ge 0 -and $pendingIndex + 1 -lt $tokens.Count) { [long]$tokens[$pendingIndex + 1] } else { $null }
            Lag = if ($lagIndex -ge 0 -and $lagIndex + 1 -lt $tokens.Count) { [long]$tokens[$lagIndex + 1] } else { $null }
            Consumers = if ($consumersIndex -ge 0 -and $consumersIndex + 1 -lt $tokens.Count) { [int]$tokens[$consumersIndex + 1] } else { $null }
            Available = $lengthResult.ExitCode -eq 0
        }
    }
    return $rows
}

function Invoke-Diagnostics {
    $configuration = Get-EnvFileValues $ligEnvFile
    $upstreamConfiguration = Get-EnvFileValues $upstreamEnvFile
    $secrets = Get-EnvFileValues $secretFile
    $apiKey = $secrets["RAGFLOW_MCP_API_KEY"]
    $apiBinding = Get-ConfigurationValue $configuration "SVR_HTTP_PORT" "127.0.0.1:42301"
    $apiPort = ($apiBinding -split ':')[-1]
    if ($apiPort -notmatch '^\d+$') {
        throw "SVR_HTTP_PORT must end with a numeric port. Current value: $apiBinding"
    }
    $apiBase = "http://127.0.0.1:$apiPort"
    $uiBinding = Get-ConfigurationValue $configuration "SVR_WEB_HTTP_PORT" "127.0.0.1:42300"
    $officialMcpBinding = Get-ConfigurationValue $configuration "SVR_MCP_PORT" "127.0.0.1:42303"
    $managementMcpBinding = Get-ConfigurationValue $configuration "RAGFLOW_MCP_LIG_PORT" "127.0.0.1:42306"
    $uiPort = ($uiBinding -split ':')[-1]
    $officialMcpPort = ($officialMcpBinding -split ':')[-1]
    $managementMcpPort = ($managementMcpBinding -split ':')[-1]
    foreach ($binding in @($uiPort, $officialMcpPort, $managementMcpPort)) {
        if ($binding -notmatch '^\d+$') { throw "Configured service port must be numeric. Current value: $binding" }
    }
    $uiUrl = "http://127.0.0.1:$uiPort/"
    $officialMcpUrl = "http://127.0.0.1:$officialMcpPort/mcp"
    $managementMcpUrl = "http://127.0.0.1:$managementMcpPort/mcp"
    $apiReachable = $false
    $serviceHealth = $null
    $dependencyHealth = $null
    $healthDetail = $null
    $apiError = $null
    $dockerVersionResult = Invoke-DockerCapture -Arguments @("version", "--format", "{{.Server.Version}}") -AllowFailure
    $dockerServerVersion = $dockerVersionResult.Lines
    $dockerError = if ($dockerVersionResult.ExitCode -eq 0) { $null } else { "Docker engine is unavailable." }

    try {
        $ping = Invoke-WebRequest -Uri "$apiBase/api/v1/system/ping" -UseBasicParsing -TimeoutSec 10
        $apiReachable = $ping.StatusCode -eq 200 -and $ping.Content.Trim() -eq "pong"
    }
    catch {
        $apiError = $_.Exception.Message
    }
    try {
        $dependencyHealth = Invoke-RestMethod -Uri "$apiBase/api/v1/system/healthz" -TimeoutSec 10
    }
    catch {
        if ($_.ErrorDetails.Message) {
            try { $dependencyHealth = $_.ErrorDetails.Message | ConvertFrom-Json }
            catch { $dependencyHealth = [pscustomobject]@{ status = "unavailable" } }
        }
    }
    $hasUsableApiKey = $apiKey -and $apiKey -notmatch 'replace-with'
    if ($apiReachable -and $hasUsableApiKey) {
        try {
            $headers = @{ Authorization = "Bearer $apiKey" }
            $response = Invoke-RestMethod -Uri "$apiBase/api/v1/system/status" -Headers $headers -TimeoutSec 10
            $serviceHealth = $response.data
        }
        catch {
            $healthDetail = "Authenticated dependency status is unavailable: $($_.Exception.Message)"
        }
    }
    elseif ($apiReachable) {
        $healthDetail = "RAGFlow API is reachable; configure RAGFLOW_MCP_API_KEY for authenticated dependency details."
    }
    $officialMcpProbe = Test-McpInitialize $officialMcpUrl
    $managementMcpProbe = Test-McpInitialize $managementMcpUrl $(if ($hasUsableApiKey) { $apiKey } else { "" })
    $ocrBinding = Get-ConfigurationValue $configuration "PADDLEOCR_PORT" "127.0.0.1:42316"
    $ocrPort = ($ocrBinding -split ':')[-1]
    $ocrUrl = "http://127.0.0.1:$ocrPort"
    $ocrHealth = $null
    try { $ocrHealth = Invoke-RestMethod -Uri "$ocrUrl/health" -TimeoutSec 10 } catch { $ocrHealth = [pscustomobject]@{ status = "unreachable"; error = $_.Exception.Message } }
    $vlBinding = Get-ConfigurationValue $configuration "PADDLEOCR_VL_PORT" "127.0.0.1:42318"
    $vlPort = ($vlBinding -split ':')[-1]
    $vlUrl = "http://127.0.0.1:$vlPort"
    $vlHealth = $null
    try { $vlHealth = Invoke-RestMethod -Uri "$vlUrl/health" -TimeoutSec 10 } catch { $vlHealth = [pscustomobject]@{ status = "not-running" } }

    $composeResult = Invoke-DockerCapture -Arguments (@($composeArguments) + $allServiceProfileArguments + @("ps", "--all", "--format", "json")) -AllowFailure
    $composeRows = @($composeResult.Lines | ForEach-Object {
        try { $_ | ConvertFrom-Json } catch { $null }
    } | Where-Object { $null -ne $_ })

    $containerNames = @($composeRows | ForEach-Object { $_.Name } | Where-Object { $_ })
    $stats = @()
    if ($containerNames.Count -gt 0) {
        $statsResult = Invoke-DockerCapture -Arguments (@("stats", "--no-stream", "--format", "{{json .}}") + $containerNames) -AllowFailure
        $stats = @($statsResult.Lines | ForEach-Object {
            try { $_ | ConvertFrom-Json } catch { $null }
        } | Where-Object { $null -ne $_ })
    }

    $timingSamples = @()
    $recentErrors = @()
    $ragflowContainer = $containerNames | Where-Object { $_ -match 'ragflow-worker-(cpu|gpu)' } | Select-Object -First 1
    if (-not $ragflowContainer) {
        $ragflowContainer = $containerNames | Where-Object { $_ -match 'ragflow-(cpu|gpu)' } | Select-Object -First 1
    }
    $ragflowHostname = $null
    $ragflowWorkerId = $null
    if ($ragflowContainer) {
        $inspectResult = Invoke-DockerCapture -Arguments @("inspect", "--format", "{{.Config.Hostname}}", $ragflowContainer) -AllowFailure
        $ragflowHostname = $inspectResult.Lines | Select-Object -Last 1
        $commandResult = Invoke-DockerCapture -Arguments @("inspect", "--format", "{{json .Config.Cmd}}", $ragflowContainer) -AllowFailure
        if ($commandResult.ExitCode -eq 0) {
            try {
                $containerCommand = @($commandResult.Lines | Select-Object -Last 1 | ConvertFrom-Json)
                $hostIdArgument = $containerCommand | Where-Object { $_ -like '--host-id=*' } | Select-Object -First 1
                if ($hostIdArgument) {
                    $ragflowWorkerId = $hostIdArgument.Substring('--host-id='.Length)
                }
            }
            catch {
                $ragflowWorkerId = $null
            }
        }
        $logsResult = Invoke-DockerCapture -Arguments @("logs", "--tail", "2000", $ragflowContainer) -AllowFailure
        $logLines = $logsResult.Lines
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
            $samples = @($_.Value)
            $latest = $samples | Select-Object -Last 1
            if ($latest -is [string]) {
                try { $latest = $latest | ConvertFrom-Json } catch { $latest = $null }
            }
            $currentTaskIds = [Collections.Generic.List[string]]::new()
            if ($latest -and $latest.current) {
                foreach ($taskId in $latest.current.PSObject.Properties.Name) {
                    $currentTaskIds.Add([string]$taskId)
                }
            }
            [pscustomobject]@{
                Worker = $_.Name
                CurrentContainer = [bool](
                    ($ragflowWorkerId -and $_.Name -match "_$([regex]::Escape($ragflowWorkerId))_") -or
                    ($ragflowHostname -and $_.Name -match [regex]::Escape($ragflowHostname)) -or
                    $_.Name -match '^task_executor(?:_[a-z0-9-]+)*_lig-(cpu|gpu)-worker_'
                )
                SamplesInLast30Minutes = $samples.Count
                LastSeen = if ($latest) { $latest.now } else { $null }
                GroupPending = if ($latest) { $latest.pending } else { $null }
                GroupLag = if ($latest) { $latest.lag } else { $null }
                CurrentTaskIds = $currentTaskIds.ToArray()
                Done = if ($latest) { $latest.done } else { $null }
                Failed = if ($latest) { $latest.failed } else { $null }
            }
        })
    }
    $redisContainer = Get-ComposeServiceContainerId "redis"
    $redisPassword = Get-ConfigurationValue $upstreamConfiguration "REDIS_PASSWORD"
    $redisQueues = @(Get-RedisQueueDiagnostics $redisContainer $redisPassword)

    $taskExecutorWorkers = [int](Get-ConfigurationValue $configuration "TASK_EXECUTOR_WORKERS" "3")
    $taskSlotsPerWorker = [int](Get-ConfigurationValue $configuration "MAX_CONCURRENT_TASKS" "1")
    $builderSlotsPerWorker = [int](Get-ConfigurationValue $configuration "MAX_CONCURRENT_CHUNK_BUILDERS" "1")
    $directWorkersPerTask = [int](Get-ConfigurationValue $configuration "PADDLEOCR_DIRECT_WORKERS" "8")
    $parserSlotsPerWorker = [Math]::Min($taskSlotsPerWorker, $builderSlotsPerWorker)
    $effectiveDirectRequests = $taskExecutorWorkers * $parserSlotsPerWorker * $directWorkersPerTask

    $report = [pscustomobject]@{
        GeneratedAt = (Get-Date).ToString("o")
        DockerServerVersion = $dockerServerVersion
        DockerError = $dockerError
        ApiReachable = $apiReachable
        Endpoints = [pscustomobject]@{
            Ui = $uiUrl
            Api = $apiBase
            OfficialMcp = $officialMcpUrl
            ManagementMcp = $managementMcpUrl
            PaddleOcr = $ocrUrl
            PaddleOcrVl = $vlUrl
        }
        Connectivity = [pscustomobject]@{
            ApiPing = $apiReachable
            DependencyHealth = $dependencyHealth
            OfficialMcp = $officialMcpProbe
            ManagementMcp = $managementMcpProbe
        }
        Configuration = [pscustomobject]@{
            Device = Get-ConfigurationValue $configuration "DEVICE"
            ApiProxyScheme = Get-ConfigurationValue $configuration "API_PROXY_SCHEME" "python"
            DocumentEngine = Get-ConfigurationValue $configuration "DOC_ENGINE"
            Profiles = Get-ConfigurationValue $configuration "COMPOSE_PROFILES"
            TaskExecutorWorkers = $taskExecutorWorkers
            ParserSlotsPerWorker = $parserSlotsPerWorker
            PaddleOcrDirectWorkersPerTask = $directWorkersPerTask
            PaddleOcrEffectiveMaxDirectRequests = $effectiveDirectRequests
            DocumentBulkSize = Get-ConfigurationValue $configuration "DOC_BULK_SIZE"
            EmbeddingBatchSize = Get-ConfigurationValue $configuration "EMBEDDING_BATCH_SIZE"
            ThreadPoolWorkers = Get-ConfigurationValue $configuration "THREAD_POOL_MAX_WORKERS"
            DoclingEnabled = Get-ConfigurationValue $configuration "USE_DOCLING"
            EmbeddingMode = if ($containerNames -contains "lig-ragflow-qwen3-embedding-1") { "optional Qwen3 TEI CPU service" } else { "configured in RAGFlow (external provider)" }
            KoreanOcr = if ($containerNames -contains "lig-ragflow-paddleocr-cpu-1") { "optional PP-OCRv5 CPU service (running)" } else { "optional PP-OCRv5 CPU service (stopped)" }
            StandaloneDeepDocEnabled = ((Get-ConfigurationValue $configuration "COMPOSE_PROFILES") -split ',' -contains 'deepdoc')
        }
        Services = $composeRows | Select-Object Name, Service, State, Health, Status, Ports
        Health = if ($serviceHealth) { [pscustomobject]@{
            DocumentEngine = $serviceHealth.doc_engine
            Storage = $serviceHealth.storage
            Database = $serviceHealth.database
            Redis = $serviceHealth.redis
        }} else { $null }
        OcrHealth = [pscustomobject]@{
            PaddleOcr = $ocrHealth
            PaddleOcrVl = $vlHealth
        }
        TaskExecutorHeartbeats = $heartbeats
        RedisQueues = $redisQueues
        CurrentTaskExecutorHeartbeatCount = @($heartbeats | Where-Object { $_.CurrentContainer }).Count
        ContainerStats = $stats | Select-Object Name, CPUPerc, MemUsage, MemPerc, BlockIO, NetIO
        RecentStageTimings = $timingSamples
        RecentErrors = $recentErrors
        HealthDetail = $healthDetail
        ApiError = $apiError
    }

    $report | ConvertTo-Json -Depth 8
}

function Wait-ContainerHealthy([string]$ContainerId, [int]$TimeoutSeconds = 180) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $result = Invoke-DockerCapture -Arguments @(
            "inspect", "--format", "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}", $ContainerId
        ) -AllowFailure
        $stateLine = $result.Lines | Select-Object -Last 1
        $state = if ($null -eq $stateLine) { "" } else { $stateLine.Trim() }
        if ($result.ExitCode -eq 0 -and $state -in @("healthy", "running")) { return }
        if ($state -in @("unhealthy", "exited", "dead")) { throw "컨테이너 복구 실패: $ContainerId ($state)" }
        Start-Sleep -Seconds 3
    } while ((Get-Date) -lt $deadline)
    throw "컨테이너가 제한 시간 내 정상화되지 않았습니다: $ContainerId"
}

function Invoke-RecoveryTest {
    $configuration = Get-EnvFileValues $ligEnvFile
    $device = (Get-ConfigurationValue $configuration "DEVICE" "cpu").Trim().ToLowerInvariant()
    $worker = Get-ComposeServiceContainerId "ragflow-worker-$device"
    $infinity = Get-ComposeServiceContainerId "infinity"
    $migration = Get-ComposeServiceContainerId "ragflow-migrate"
    foreach ($required in @($worker, $infinity, $migration)) {
        if (-not $required) { throw "복구 시험에 필요한 컨테이너가 없습니다. 먼저 RAGFlow를 시작하십시오." }
    }
    $migrationResult = Invoke-DockerCapture -Arguments @(
        "inspect", "--format", "{{.State.Status}} {{.State.ExitCode}}", $migration
    ) -AllowFailure
    if (($migrationResult.Lines | Select-Object -Last 1).Trim() -ne "exited 0") {
        throw "DB 마이그레이션 작업이 성공 상태가 아닙니다: $(($migrationResult.Lines -join ' ').Trim())"
    }

    Write-Warning "격리 worker와 Infinity를 순서대로 재시작합니다. 실행 중 문서는 lease 기반으로 재개되지만 시험 중 처리가 잠시 멈춥니다."
    Invoke-Docker @("restart", $worker)
    Wait-ContainerHealthy $worker
    Invoke-Docker @("restart", $infinity)
    Wait-ContainerHealthy $infinity

    $binding = Get-ConfigurationValue $configuration "SVR_HTTP_PORT" "127.0.0.1:42301"
    $port = ($binding -split ':')[-1]
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/v1/system/healthz" -TimeoutSec 15
    if (-not $health) { throw "재시작 후 API 의존성 상태를 확인할 수 없습니다." }
    Write-Host "DB 마이그레이션, worker 재시작, Infinity 재시작, API 의존성 상태 시험을 통과했습니다."
}

switch ($Action) {
    "config" {
        Assert-LigConfiguration
        Invoke-Compose @("config", "--quiet")
        Assert-OcrDeviceTopology
        Write-Host "RAGFlow Compose 설정이 정상입니다."
    }
    "pull" {
        Assert-FreeSpace
        Invoke-Docker @("pull", "infiniflow/ragflow:v0.26.4")
        Invoke-Compose @("pull", "infinity", "mysql", "minio", "redis")
    }
    "ui-build" {
        Assert-FreeSpace
        Invoke-Docker @("build", "--file", $uiDockerfile, "--tag", "lig/ragflow-ui:v0.26.4-4", $workspaceDirectory)
        Write-Host "Built lig/ragflow-ui:v0.26.4-4"
    }
    "mcp-build" {
        Assert-FreeSpace
        Invoke-Docker @("build", "--file", $mcpDockerfile, "--tag", "lig/ragflow-mcp:v0.26.4-3", $mcpDirectory)
        Write-Host "Built lig/ragflow-mcp:v0.26.4-3"
    }
    "ocr-build" {
        Assert-FreeSpace
        Invoke-Docker @("build", "--file", $ocrDockerfile, "--tag", "lig/paddleocr-ko:v0.26.4-4", $ocrDirectory)
        Write-Host "Built lig/paddleocr-ko:v0.26.4-4"
    }
    "gpu-build" {
        Assert-FreeSpace
        Invoke-Docker @("build", "--file", $gpuUiDockerfile, "--tag", "lig/ragflow-ui-gpu:v0.26.4-4", $workspaceDirectory)
        Write-Host "RAGFlow/DeepDOC용 CUDA 이미지를 빌드했습니다. 일반 PaddleOCR는 CPU 이미지를 공용으로 사용합니다."
    }
    "embedding-build" {
        Assert-FreeSpace
        Invoke-Docker @("build", "--file", $embeddingModelDockerfile, "--tag", "lig/qwen3-embedding-tei:0.6b-1", $embeddingDirectory)
        Invoke-Docker @("build", "--file", $embeddingAdapterDockerfile, "--tag", "lig/qwen3-embedding-adapter:0.6b-1", $embeddingDirectory)
        Write-Host "Built Qwen3 Embedding 0.6B TEI CPU and query adapter images."
    }
    "paddleocr-vl-build" {
        Assert-FreeSpace
        $configuration = Get-EnvFileValues $ligEnvFile
        $pipelineBaseImage = Get-ConfigurationValue $configuration "PADDLEOCR_VL_API_BASE_IMAGE"
        $pipelineImage = Get-ConfigurationValue $configuration "PADDLEOCR_VL_API_IMAGE" "lig/paddleocr-vl-pipeline-cpu:1.6-1"
        $vlmBaseImage = Get-ConfigurationValue $configuration "PADDLEOCR_VL_VLM_IMAGE"
        $vlmImage = Get-ConfigurationValue $configuration "PADDLEOCR_VL_VLM_RUNTIME_IMAGE" "lig/paddleocr-vl-vlm:1.6-2"
        $gatewayImage = Get-ConfigurationValue $configuration "PADDLEOCR_VL_GATEWAY_IMAGE" "lig/paddleocr-vl-gateway:1.6-1"
        if ([string]::IsNullOrWhiteSpace($pipelineBaseImage)) { throw "PaddleOCR-VL pipeline 기반 이미지 설정이 없습니다." }
        Invoke-Docker @("build", "--file", $ocrVlPipelineCpuDockerfile, "--build-arg", "BASE_IMAGE=$pipelineBaseImage", "--tag", $pipelineImage, $ocrVlDirectory)
        Invoke-Docker @("build", "--file", $ocrVlVlmDockerfile, "--build-arg", "BASE_IMAGE=$vlmBaseImage", "--tag", $vlmImage, $ocrVlDirectory)
        Invoke-Docker @("build", "--file", $ocrVlDockerfile, "--tag", $gatewayImage, $ocrVlDirectory)
        Write-Host "PaddleOCR-VL-1.6 CPU pipeline과 RAGFlow 호환 게이트웨이 이미지를 빌드했습니다."
    }
    "paddleocr-vl-pull" {
        Assert-FreeSpace
        $configuration = Get-EnvFileValues $ligEnvFile
        foreach ($image in @(
            (Get-ConfigurationValue $configuration "PADDLEOCR_VL_API_BASE_IMAGE"),
            (Get-ConfigurationValue $configuration "PADDLEOCR_VL_VLM_IMAGE")
        )) {
            if ([string]::IsNullOrWhiteSpace($image)) { throw "PaddleOCR-VL 공식 이미지 설정이 없습니다." }
            Invoke-Docker @("pull", $image)
        }
        Write-Host "PaddleOCR-VL-1.6 공식 오프라인 pipeline 기반 이미지와 VLM 이미지를 받았습니다."
    }
    "build" {
        Assert-FreeSpace
        Invoke-Docker @("build", "--file", $uiDockerfile, "--tag", "lig/ragflow-ui:v0.26.4-4", $workspaceDirectory)
        Invoke-Docker @("build", "--file", $mcpDockerfile, "--tag", "lig/ragflow-mcp:v0.26.4-3", $mcpDirectory)
        Invoke-Docker @("build", "--file", $ocrDockerfile, "--tag", "lig/paddleocr-ko:v0.26.4-4", $ocrDirectory)
        Write-Host "Built LIG UI, management MCP, and Korean PaddleOCR images."
    }
    "start" {
        Assert-LigConfiguration
        Assert-OcrDeviceTopology
        Assert-FreeSpace
        $configuration = Get-EnvFileValues $ligEnvFile
        $device = (Get-ConfigurationValue $configuration "DEVICE" "cpu").Trim().ToLowerInvariant()
        if ($device -notin @("cpu", "gpu")) {
            throw "DEVICE must be cpu or gpu. Current value: $device"
        }

        $ragflowImage = if ($device -eq "gpu") {
            Get-ConfigurationValue $configuration "RAGFLOW_GPU_IMAGE"
        } else {
            Get-ConfigurationValue $configuration "RAGFLOW_IMAGE"
        }
        $mcpImage = Get-ConfigurationValue $configuration "RAGFLOW_MCP_LIG_IMAGE" "lig/ragflow-mcp:v0.26.4-3"
        foreach ($requiredImage in @($ragflowImage, $mcpImage)) {
            if ([string]::IsNullOrWhiteSpace($requiredImage)) {
                throw "필수 이미지 설정이 없습니다. RAGFLOW_IMAGE, RAGFLOW_GPU_IMAGE, RAGFLOW_MCP_LIG_IMAGE를 확인하십시오."
            }
        }

        $ragflowImageInspect = Invoke-DockerCapture -Arguments @("image", "inspect", "--format", "{{.Id}}", $ragflowImage) -AllowFailure
        if ($ragflowImageInspect.ExitCode -ne 0) {
            if ($device -eq "gpu") {
                throw "Required GPU RAGFlow image is missing: $ragflowImage. Run gpu-build or import the GPU air-gap bundle first."
            }
            if (-not (Test-Path -LiteralPath $uiDockerfile -PathType Leaf)) {
                throw "RAGFlow image is missing and its Dockerfile is unavailable: $ragflowImage"
            }
            Invoke-Docker @("build", "--file", $uiDockerfile, "--tag", $ragflowImage, $workspaceDirectory)
        }

        $mcpImageInspect = Invoke-DockerCapture -Arguments @("image", "inspect", "--format", "{{.Id}}", $mcpImage) -AllowFailure
        if ($mcpImageInspect.ExitCode -ne 0) {
            if (-not (Test-Path -LiteralPath $mcpDockerfile -PathType Leaf)) {
                throw "Management MCP image is missing and its Dockerfile is unavailable: $mcpDockerfile"
            }
            Invoke-Docker @("build", "--file", $mcpDockerfile, "--tag", $mcpImage, $mcpDirectory)
        }
        # Start asynchronously. RAGFlow's health check verifies every backing
        # service and can remain in "Waiting" long after the containers have
        # started, which makes an otherwise successful start look hung.
        # 선택 실행한 OCR/embedding 프로필은 이 명령의 활성 프로필에 포함되지
        # 않을 수 있으므로 orphan으로 제거하지 않습니다. 전체 정리는 stop이 담당합니다.
        Invoke-Compose @("up", "-d")
        Invoke-Compose @("ps")
    }
    "paddleocr-start" {
        Assert-FreeSpace
        $configuration = Get-EnvFileValues $ligEnvFile
        $ocrImage = Get-ConfigurationValue $configuration "PADDLEOCR_IMAGE"
        if ([string]::IsNullOrWhiteSpace($ocrImage)) {
            throw "PADDLEOCR_IMAGE 설정이 없습니다."
        }
        $imageInspect = Invoke-DockerCapture -Arguments @("image", "inspect", "--format", "{{.Id}}", $ocrImage) -AllowFailure
        if ($imageInspect.ExitCode -ne 0) {
            throw "선택형 PaddleOCR 이미지가 없습니다: $ocrImage. ocr-build를 먼저 실행하거나 에어갭 번들을 가져오십시오."
        }
        Invoke-Compose @("--profile", "paddleocr", "up", "-d", "paddleocr-cpu")
        Invoke-Compose @("--profile", "paddleocr", "ps", "paddleocr-cpu")
    }
    "paddleocr-stop" {
        Invoke-Compose @("--profile", "paddleocr", "stop", "paddleocr-cpu")
    }
    "paddleocr-status" {
        Invoke-Compose @("--profile", "paddleocr", "ps", "paddleocr-cpu")
    }
    "paddleocr-test" {
        $container = Get-ComposeServiceContainerId "paddleocr-cpu"
        if (-not $container) {
            throw "PaddleOCR 컨테이너가 실행 중이 아닙니다. paddleocr-start를 먼저 실행하십시오."
        }
        $health = Invoke-DockerCapture -Arguments @("inspect", "--format", "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}", $container) -AllowFailure
        if ($health.ExitCode -ne 0 -or ($health.Lines -join "").Trim() -ne "healthy") {
            throw "PaddleOCR 상태가 healthy가 아닙니다: $(($health.Lines -join '').Trim())"
        }
        Write-Host "PaddleOCR PP-OCRv5 CPU 서비스가 정상입니다."
    }
    "embedding-start" {
        Assert-FreeSpace
        foreach ($image in @("lig/qwen3-embedding-tei:0.6b-1", "lig/qwen3-embedding-adapter:0.6b-1")) {
            $imageInspect = Invoke-DockerCapture -Arguments @("image", "inspect", "--format", "{{.Id}}", $image) -AllowFailure
            if ($imageInspect.ExitCode -ne 0) {
                throw "Optional embedding image is missing: $image. Run embedding-build or import the air-gap bundle first."
            }
        }
        Invoke-Compose @("--profile", "embedding-cpu", "up", "-d", "qwen3-embedding-tei", "qwen3-embedding")
        Invoke-Compose @("--profile", "embedding-cpu", "ps", "qwen3-embedding-tei", "qwen3-embedding")
    }
    "paddleocr-vl-start" {
        Assert-FreeSpace
        $configuration = Get-EnvFileValues $ligEnvFile
        $images = @(
            (Get-ConfigurationValue $configuration "PADDLEOCR_VL_API_IMAGE"),
            (Get-ConfigurationValue $configuration "PADDLEOCR_VL_VLM_RUNTIME_IMAGE"),
            (Get-ConfigurationValue $configuration "PADDLEOCR_VL_GATEWAY_IMAGE" "lig/paddleocr-vl-gateway:1.6-1")
        )
        foreach ($image in $images) {
            $inspect = Invoke-DockerCapture -Arguments @("image", "inspect", "--format", "{{.Id}}", $image) -AllowFailure
            if ($inspect.ExitCode -ne 0) {
                throw "PaddleOCR-VL 이미지가 없습니다: $image. paddleocr-vl-pull 또는 paddleocr-vl-build를 먼저 실행하십시오."
            }
        }
        $pipelineCheck = Invoke-DockerCapture -Arguments @(
            "run", "--rm", "--entrypoint", "python", $images[0], "-c",
            "import paddle; assert not paddle.device.is_compiled_with_cuda(); print('PaddleOCR-VL pipeline:', paddle.__version__, 'CPU')"
        ) -AllowFailure
        if ($pipelineCheck.ExitCode -ne 0) {
            throw "PaddleOCR-VL pipeline 이미지가 CPU 전용이 아닙니다. paddleocr-vl-build를 다시 실행하십시오."
        }
        $pipelineCheck.Lines | ForEach-Object { Write-Host $_ }
        Write-Host "PaddleOCR-VL 시작 구성: VL 레이아웃=CPU, VL 0.9B VLM=GPU (일반 PP-OCRv5는 별도 선택 실행)"
        Write-Host "VLM 설정: GPU 비율 $(Get-ConfigurationValue $configuration 'PADDLEOCR_VL_GPU_MEMORY_UTILIZATION' '0.60'), 컨텍스트 $(Get-ConfigurationValue $configuration 'PADDLEOCR_VL_MAX_MODEL_LEN' '16384'), 배치 토큰 $(Get-ConfigurationValue $configuration 'PADDLEOCR_VL_MAX_NUM_BATCHED_TOKENS' '16384'), API 서버 $(Get-ConfigurationValue $configuration 'PADDLEOCR_VL_API_SERVER_COUNT' '1')"
        $gpuCheck = Invoke-DockerCapture -Arguments @(
            "run", "--rm", "--gpus", "all", "--entrypoint", "nvidia-smi", $images[1],
            "--query-gpu=name,memory.total,memory.used,memory.free,driver_version",
            "--format=csv,noheader"
        ) -AllowFailure
        if ($gpuCheck.ExitCode -ne 0) {
            throw "NVIDIA GPU를 PaddleOCR-VL 컨테이너에서 사용할 수 없습니다. 드라이버와 NVIDIA Container Toolkit을 확인하십시오."
        }
        Write-Host "PaddleOCR-VL 시작 전 GPU 상태:"
        $gpuCheck.Lines | ForEach-Object { Write-Host $_ }
        Invoke-Compose @("--profile", "paddleocr-vl", "up", "-d", "paddleocr-vl-vlm", "paddleocr-vl-api", "paddleocr-vl")
        Invoke-Compose @("--profile", "paddleocr-vl", "ps", "paddleocr-vl-vlm", "paddleocr-vl-api", "paddleocr-vl")
    }
    "paddleocr-vl-stop" {
        Invoke-Compose @("--profile", "paddleocr-vl", "stop", "paddleocr-vl", "paddleocr-vl-api", "paddleocr-vl-vlm")
    }
    "paddleocr-vl-status" {
        Invoke-Compose @("--profile", "paddleocr-vl", "ps", "paddleocr-vl-vlm", "paddleocr-vl-api", "paddleocr-vl")
        $configuration = Get-EnvFileValues $ligEnvFile
        Write-Host ""
        Write-Host "장치 배치: VL 레이아웃=CPU | VL VLM=GPU | 일반 PP-OCRv5=별도 선택 실행"
        Write-Host "VLM 메모리 비율=$(Get-ConfigurationValue $configuration 'PADDLEOCR_VL_GPU_MEMORY_UTILIZATION' '0.60'), 최대 배치 토큰=$(Get-ConfigurationValue $configuration 'PADDLEOCR_VL_MAX_NUM_BATCHED_TOKENS' '16384'), 최대 시퀀스=$(Get-ConfigurationValue $configuration 'PADDLEOCR_VL_MAX_NUM_SEQS' '8')"
        $vlmContainer = Get-ComposeServiceContainerId "paddleocr-vl-vlm"
        Show-PaddleOcrVlGpuSummary $vlmContainer
        if ($vlmContainer) {
            $vlmLogs = Invoke-DockerCapture -Arguments @("logs", "--tail", "300", $vlmContainer) -AllowFailure
            $memoryErrors = @($vlmLogs.Lines | Where-Object { $_ -match '(?i)(No available memory for the cache blocks|out of memory|CUDA.*memory|KV cache)' } | Select-Object -Last 10)
            if ($memoryErrors.Count) {
                Write-Warning "최근 VLM 메모리 오류가 발견됐습니다:"
                $memoryErrors | ForEach-Object { Write-Host $_ }
            }
        }
    }
    "paddleocr-vl-test" {
        $configuration = Get-EnvFileValues $ligEnvFile
        $binding = Get-ConfigurationValue $configuration "PADDLEOCR_VL_PORT" "127.0.0.1:42318"
        $port = ($binding -split ':')[-1]
        if ($port -notmatch '^\d+$') { throw "PADDLEOCR_VL_PORT는 숫자 포트로 끝나야 합니다. 현재 값: $binding" }
        foreach ($service in @("paddleocr-vl-vlm", "paddleocr-vl-api")) {
            $containerId = Get-ComposeServiceContainerId $service
            if (-not $containerId) { throw "$service 컨테이너가 없습니다." }
            $probe = Invoke-DockerCapture -Arguments @("exec", $containerId, "curl", "-fsS", "http://127.0.0.1:8080/health") -AllowFailure
            if ($probe.ExitCode -ne 0) { throw "$service 내부 상태 확인에 실패했습니다." }
            Write-Host "$service 내부 상태 정상"
        }
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/health" -TimeoutSec 15
        if ($health.status -ne "ok" -or $health.model -ne "PaddleOCR-VL-1.6") {
            throw "PaddleOCR-VL 상태 응답이 올바르지 않습니다."
        }
        Write-Host "PaddleOCR-VL-1.6 VLM, CPU pipeline, RAGFlow 호환 게이트웨이가 모두 정상입니다."
    }
    "embedding-stop" {
        Invoke-Compose @("--profile", "embedding-cpu", "stop", "qwen3-embedding", "qwen3-embedding-tei")
    }
    "embedding-status" {
        Invoke-Compose @("--profile", "embedding-cpu", "ps", "qwen3-embedding-tei", "qwen3-embedding")
    }
    "embedding-test" {
        $configuration = Get-EnvFileValues $ligEnvFile
        $binding = Get-ConfigurationValue $configuration "QWEN3_EMBEDDING_PORT" "127.0.0.1:42317"
        $port = ($binding -split ':')[-1]
        if ($port -notmatch '^\d+$') { throw "QWEN3_EMBEDDING_PORT must end with a numeric port. Current value: $binding" }
        $baseUrl = "http://127.0.0.1:$port"
        $health = $null
        for ($attempt = 1; $attempt -le 12; $attempt++) {
            try {
                $health = Invoke-RestMethod -Uri "$baseUrl/health" -TimeoutSec 10
                if ($health.status -eq "ok") { break }
            }
            catch {
                if ($attempt -eq 12) { throw }
            }
            Start-Sleep -Seconds 5
        }
        if ($health.status -ne "ok" -or $health.model -ne "Qwen/Qwen3-Embedding-0.6B") {
            throw "Unexpected embedding health response."
        }
        $body = @{ inputs = @("국방 문서 검색 시험", "defense document retrieval test") } | ConvertTo-Json -Compress
        # Windows PowerShell 5.1 otherwise encodes a string request body with
        # the active ANSI code page. Send explicit UTF-8 bytes for Korean text.
        $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($body)
        $vectors = Invoke-RestMethod -Uri "$baseUrl/embed" -Method Post -ContentType "application/json; charset=utf-8" -Body $bodyBytes -TimeoutSec 120
        if (@($vectors).Count -ne 2 -or @($vectors[0]).Count -ne 1024 -or @($vectors[1]).Count -ne 1024) {
            throw "Embedding response must contain two 1024-dimensional vectors."
        }
        Write-Host "Qwen3 embedding health and 1024-dimensional batch inference passed."
    }
    "stop" {
        Invoke-Compose ($allServiceProfileArguments + @("down", "--remove-orphans"))
    }
    "status" {
        Invoke-Compose ($allServiceProfileArguments + @("ps", "--all"))
        Invoke-Docker @("system", "df")
    }
    "diagnostics" { Invoke-Diagnostics }
    "recovery-test" { Invoke-RecoveryTest }
    "logs" {
        Invoke-Compose ($allServiceProfileArguments + @("logs", "--tail", "200"))
    }
}
