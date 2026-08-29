param(
    [string]$Namespace = "lig-ragflow",
    [string]$Name = "lig-ragflow-secrets"
)

$ErrorActionPreference = "Stop"

function New-RandomValue([int]$Bytes = 32) {
    $buffer = [byte[]]::new($Bytes)
    [Security.Cryptography.RandomNumberGenerator]::Fill($buffer)
    return [Convert]::ToBase64String($buffer)
}

if (-not (Get-Command kubectl -CommandType Application -ErrorAction SilentlyContinue)) {
    throw "kubectl을 찾을 수 없습니다."
}

& kubectl get namespace $Namespace 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    & kubectl create namespace $Namespace | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "namespace 생성 실패: $Namespace" }
}

$mysqlPassword = New-RandomValue
$minioPassword = New-RandomValue
$secret = [ordered]@{
    apiVersion = "v1"
    kind = "Secret"
    metadata = [ordered]@{ name = $Name; namespace = $Namespace }
    type = "Opaque"
    stringData = [ordered]@{
        MYSQL_PASSWORD = $mysqlPassword
        MYSQL_ROOT_PASSWORD = $mysqlPassword
        MINIO_USER = "rag_flow"
        MINIO_ROOT_USER = "rag_flow"
        MINIO_PASSWORD = $minioPassword
        MINIO_ROOT_PASSWORD = $minioPassword
        REDIS_PASSWORD = New-RandomValue
        PADDLEOCR_INTERNAL_TOKEN = New-RandomValue
        PADDLEOCR_VL_INTERNAL_TOKEN = New-RandomValue
        LIG_DOCUMENT_PASSWORD_KEY = New-RandomValue 32
        LIG_DOCUMENT_PASSWORD_KEY_ID = "primary"
        LIG_DOCUMENT_PASSWORD_PREVIOUS_KEYS = ""
    }
}

$json = $secret | ConvertTo-Json -Depth 6 -Compress
$json | & kubectl apply -f -
if ($LASTEXITCODE -ne 0) { throw "Secret 적용 실패" }
Write-Host "Secret을 생성했습니다: $Namespace/$Name"
Write-Host "재해 복구를 위해 Kubernetes Secret을 암호화된 관리 저장소에 백업하십시오."

