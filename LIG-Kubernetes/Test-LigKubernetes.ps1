$ErrorActionPreference = "Stop"
$chartDirectory = $PSScriptRoot
if (-not (Get-Command helm -CommandType Application -ErrorAction SilentlyContinue)) {
    throw "helm을 찾을 수 없습니다."
}

& helm lint $chartDirectory
if ($LASTEXITCODE -ne 0) { throw "기본 Helm lint 실패" }

$basic = (& helm template lig $chartDirectory --namespace lig-ragflow) -join "`n"
if ($LASTEXITCODE -ne 0) { throw "기본 Helm 렌더링 실패" }

$all = (& helm template lig $chartDirectory --namespace lig-ragflow `
    --set paddleocr.enabled=true `
    --set embedding.enabled=true `
    --set paddleocrVl.enabled=true `
    --set ragflow.worker.gpu.enabled=true) -join "`n"
if ($LASTEXITCODE -ne 0) { throw "전체 옵션 Helm 렌더링 실패" }

foreach ($rendered in @($basic, $all)) {
    if ($rendered -match 'allkeys-lru|--maxmemory\s+128mb') {
        throw "Redis 큐 퇴행 설정이 렌더링 결과에 있습니다."
    }
    if ($rendered -notmatch '--maxmemory-policy\s+-\s+noeviction') {
        throw "Redis noeviction 설정이 없습니다."
    }
    if ($rendered -notmatch '--host-id=\$\(POD_NAME\)') {
        throw "Worker의 Pod별 고유 host ID 설정이 없습니다."
    }
    if ($rendered -notmatch 'name: lig-lig-ragflow-internal') {
        throw "내부 API 전용 ClusterIP Service가 없습니다."
    }
}

$publicService = $basic.Split("---") | Where-Object {
    $_ -match '(?m)^kind: Service$' -and $_ -match '(?m)^  name: lig-lig-ragflow$'
} | Select-Object -First 1
if (-not $publicService -or $publicService -match 'port: 938[0-2]') {
    throw "웹 Service에 내부 API·관리·MCP 포트가 노출되어 있습니다."
}
if ($basic -notmatch 'http://lig-lig-ragflow-internal:9380') {
    throw "관리 MCP가 내부 API Service를 사용하지 않습니다."
}

if ($basic -match 'nvidia.com/gpu') { throw "기본 CPU 렌더링에 GPU 할당이 있습니다." }
if ($all -notmatch 'nvidia.com/gpu') { throw "GPU 렌더링에 GPU 할당이 없습니다." }
if ($all -notmatch 'name: paddleocr-vlm-server') { throw "PaddleOCR-VL 고정 VLM DNS Service가 없습니다." }
if ($all -notmatch 'replicas: 1\s+strategy:\s+type: Recreate') { throw "OCR 단일 replica/Recreate 정책이 없습니다." }

& helm template invalid $chartDirectory --set ragflow.api.replicas=2 *> $null
if ($LASTEXITCODE -eq 0) { throw "API replica 안전 검증이 작동하지 않습니다." }
& helm template invalid $chartDirectory --set redis.enabled=false *> $null
if ($LASTEXITCODE -eq 0) { throw "필수 StatefulSet 검증이 작동하지 않습니다." }

Write-Host "LIG Kubernetes Helm 계약 검증 통과"
