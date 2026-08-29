param(
    [string]$Namespace = "lig-ragflow",
    [string]$Release = "lig",
    [string]$ValuesFile = "",
    [string]$SecretName = "lig-ragflow-secrets",
    [switch]$Wait
)

$ErrorActionPreference = "Stop"
$chartDirectory = $PSScriptRoot
foreach ($command in @("kubectl", "helm")) {
    if (-not (Get-Command $command -CommandType Application -ErrorAction SilentlyContinue)) {
        throw "$command 명령을 찾을 수 없습니다."
    }
}

& kubectl get namespace $Namespace 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    & kubectl create namespace $Namespace | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "namespace 생성 실패: $Namespace" }
}

& kubectl --namespace $Namespace get secret $SecretName 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Secret이 없습니다. 먼저 New-LigRagFlowSecret.ps1을 실행하십시오."
}

$arguments = @(
    "upgrade", "--install", $Release, $chartDirectory,
    "--namespace", $Namespace,
    "--atomic", "--timeout", "20m",
    "--set-string", "secret.existingSecret=$SecretName"
)
if ($ValuesFile) {
    $resolvedValues = (Resolve-Path -LiteralPath $ValuesFile).Path
    $arguments += @("--values", $resolvedValues)
}
if ($Wait) { $arguments += "--wait" }

& helm @arguments
if ($LASTEXITCODE -ne 0) { throw "Helm 설치 실패" }
& kubectl --namespace $Namespace get pods,services,persistentvolumeclaims
