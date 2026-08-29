# LIG AI Knowledge Hub Kubernetes 준비본

이 Chart는 `LIG-Deployment/docker-compose.lig.yml`의 동작을 Kubernetes에 맞게 옮긴 준비본입니다. `RAGFlow/helm` 원본은 수정하지 않습니다.

## 배치 구조

- RAGFlow API: 단일 Deployment. initContainer가 MySQL·Redis·MinIO·Infinity를 기다린 뒤 스키마 마이그레이션을 실행합니다.
- RAGFlow Worker: 별도 Deployment. Pod 이름을 consumer ID로 사용하므로 `replicas`를 늘려도 Redis consumer가 충돌하지 않습니다.
- MySQL, Redis, MinIO, Infinity: 각각 단일 StatefulSet과 보존 PVC를 사용합니다.
- 관리 MCP: 별도 Deployment와 Service이며 클라이언트의 개인 RAGFlow API 키를 Bearer로 받습니다.
- 일반 PaddleOCR, Qwen3 임베딩, PaddleOCR-VL: 기본 비활성화이며 values에서 필요한 항목만 켭니다.

일반 PaddleOCR와 PaddleOCR-VL gateway는 Job 상태를 프로세스 메모리에 보관하므로 replica를 1개로 고정했습니다. 처리량은 RAGFlow Worker 수로 늘리되 OCR Pod 자체를 수평 확장하지 마십시오.

## 사전 준비

1. Kubernetes 1.28 이상, Helm 3, 동적 PVC를 지원하는 StorageClass를 준비합니다.
2. 폐쇄망 Registry를 준비하고 에어갭 아카이브를 `airgap-import.ps1`로 불러옵니다.
3. `Push-LigImages.ps1 -Registry registry.internal -IncludeGpu -IncludeEmbedding -IncludePaddleOcr -IncludePaddleOcrVl`처럼 필요한 이미지만 Registry로 올립니다.
4. `values-airgap.example.yaml`을 복사해 Registry와 StorageClass를 수정합니다.
5. GPU 기능은 NVIDIA Device Plugin 또는 GPU Operator가 `nvidia.com/gpu` 리소스를 제공해야 합니다.

이미지를 각 노드의 containerd에 직접 넣을 수도 있지만 Pod가 다른 노드로 이동하면 다시 반입해야 합니다. 사내 Registry 방식이 재시작과 노드 교체에 안전합니다.

## 설치

PowerShell에서 다음 순서로 실행합니다.

```powershell
pwsh ./New-LigRagFlowSecret.ps1 -Namespace lig-ragflow
pwsh ./Install-LigRagFlow.ps1 -Namespace lig-ragflow -ValuesFile ./values-airgap.yaml -Wait
```

실제 클러스터로 옮기기 전 로컬 렌더링 검증은 다음과 같습니다.

```powershell
pwsh ./Test-LigKubernetes.ps1
```

이전용 Helm 패키지와 설명서·설정 예제를 별도 폴더로 묶으려면 다음을 실행합니다. 이 명령은 기존 Docker 에어갭 번들을 수정하거나 다시 만들지 않습니다.

```powershell
pwsh ./Export-LigKubernetes.ps1 -Destination D:\Transfer\LIG-Kubernetes
```

기본 Secret 이름을 바꾸려면 두 스크립트에 같은 `-Name`/`-SecretName`을 전달합니다. 설치 스크립트가 Chart 값도 같은 이름으로 고정합니다. Secret 특히 `LIG_DOCUMENT_PASSWORD_KEY`를 잃으면 저장된 PDF 암호를 복호화할 수 없으므로 반드시 별도 백업하십시오.

## 선택 기능

일반 CPU PaddleOCR:

```yaml
paddleocr:
  enabled: true
```

Qwen3 CPU 임베딩:

```yaml
embedding:
  enabled: true
```

PaddleOCR-VL GPU:

```yaml
paddleocrVl:
  enabled: true
  gpu:
    nodeSelector:
      accelerator: nvidia
```

DeepDOC GPU Worker:

```yaml
ragflow:
  worker:
    gpu:
      enabled: true
      nodeSelector:
        accelerator: nvidia
```

GPU는 Kubernetes extended resource 특성상 `resources.limits` 아래의 `nvidia.com/gpu`가 할당 수단입니다. CPU와 시스템 메모리는 limit를 두지 않고 필요한 경우 `resources.requests`만 설정합니다.

## 운영 주의사항

- 전용 namespace에 한 release만 설치하십시오. PaddleOCR 오프라인 pipeline이 `paddleocr-vlm-server` DNS를 사용합니다.
- API replica 기본값 1은 동시 사용자 수를 1명으로 제한한다는 뜻이 아닙니다. API 프로세스 내부 worker가 동시 요청을 처리합니다.
- 웹 Service와 API·관리·공식 MCP용 내부 ClusterIP Service를 분리했습니다. 웹 Service를 LoadBalancer로 바꾸더라도 9380~9382 포트는 외부에 함께 노출되지 않습니다.
- Worker 확장은 `ragflow.worker.replicas`를 조정합니다. Pod당 parser 수는 `executorsPerPod`이며 두 값을 곱한 수가 전체 동시 문서 task 수입니다.
- Redis는 큐이므로 `noeviction`, `maxmemory=0`을 유지합니다.
- Infinity는 단일 writer StatefulSet으로 유지하고 종료 유예시간 60초를 줄이지 마십시오.
- PVC에는 Helm 삭제 보존 정책을 적용했습니다. Chart 삭제 후 데이터까지 지우려면 PVC를 별도로 명시해 삭제해야 합니다.
- 일반 OCR/VL의 진행 중 Job은 해당 Pod가 재시작되면 유실됩니다. RAGFlow의 작업 lease와 stale claim이 재처리하지만, OCR Pod 업데이트는 작업이 없을 때 수행하십시오.

## 이전 전에 확인할 값

- 실제 Kubernetes 배포판과 버전
- StorageClass 이름과 확장 가능 여부
- Ingress Controller 및 사내 DNS/TLS
- Registry 주소와 인증 Secret
- GPU 노드 label, NVIDIA Device Plugin 리소스 이름
- PVC 용량과 백업 저장소

## Docker와 Kubernetes 병행 지원

`LIG-Deployment/`의 Docker Compose 배포와 이 Chart는 서로 독립적입니다. Kubernetes를 추가해도 기존 `install.ps1`, `start.ps1`, `lig-ragflow.ps1`의 실행 방식과 포트, 볼륨은 바뀌지 않습니다. 같은 데이터 디렉터리를 Docker와 Kubernetes가 동시에 마운트해서는 안 되며, 두 방식을 같은 호스트에서 시험할 때는 서비스 포트와 저장 경로를 분리하십시오.

## 기존 Docker 데이터 이전

Chart 준비와 실제 데이터 이전은 별도 단계입니다. 새 Kubernetes 환경을 먼저 빈 데이터로 검증한 뒤 유지보수 시간에 Docker 서비스를 멈추고 `LIG-Deployment/backup-ragflow.ps1 -LeaveStopped`로 일관된 볼륨 백업을 만드십시오. 실행 중인 MySQL·MinIO·Infinity 디렉터리를 직접 복사하면 안 됩니다.

Docker 볼륨 백업을 Kubernetes PVC에 복원하는 작업은 실제 StorageClass, CSI snapshot 기능, 백업 반입 경로를 확인한 다음 수행해야 합니다. 그 정보 없이 범용 자동 복원 스크립트를 실행하면 RWO PVC 중복 마운트나 기존 PVC 덮어쓰기가 발생할 수 있으므로 이 준비본에는 자동 실행을 넣지 않았습니다. 실제 클러스터 정보가 정해지면 다음을 확정합니다.

- 신규 설치인지 기존 Docker 데이터 승계인지
- 백업 파일을 올릴 임시 PVC 또는 사내 오브젝트 저장소
- StatefulSet 정지와 PVC 단독 마운트 절차
- 기존 MySQL·Redis·MinIO 비밀번호와 `LIG_DOCUMENT_PASSWORD_KEY` 승계
- 복원 후 Infinity 인덱스와 문서 개수 대조
