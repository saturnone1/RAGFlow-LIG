# LIG RAGFlow 경량 배포

이 구성은 공식 RAGFlow `v0.26.4`를 수정하지 않고 Windows 노트북과 에어갭 환경에서 관리하기 위한 오버레이입니다. 특정 PDF에 종속되지 않으며, 문서 저장·파싱·청킹·검색은 RAGFlow가 담당합니다.

## 선택한 구성

- 문서 엔진: Elasticsearch 대신 Infinity
- 실행 장치: CPU
- 내부 서비스: RAGFlow, LIG 관리 MCP, Infinity, MySQL, MinIO, Valkey. Ollama는 선택 사항
- 기본 임베딩: NVIDIA 공개 API의 `nvidia/llama-nemotron-embed-vl-1b-v2`
- 에어갭 대체 임베딩: Ollama의 다국어 `qwen3-embedding:0.6b`(양자화 모델 약 639 MB)
- 제외: Kibana, Sandbox, TEI, 별도 Docling 서비스
- 포트: 모두 `127.0.0.1`에만 공개
- 포트 블록: 기존 MCP 서버의 `42180`~`42198` 다음 대역인 `42200`~`42215`
- 웹 UI: `http://127.0.0.1:42200`
- REST API: `http://127.0.0.1:42201`
- 공식 MCP: `http://127.0.0.1:42203/mcp`
- LIG 관리 MCP: `http://127.0.0.1:42206/mcp`
- 로그: 컨테이너마다 최대 20 MiB 파일 3개
- 동시 처리: task executor 2개, 문서 bulk 2개, 임베딩 배치 8개, 내부 thread pool 12개
- 메모리: RAGFlow 8 GiB, Infinity 2 GiB, MySQL 1.25 GiB, MinIO 768 MiB, Valkey 256 MiB 상한. Ollama 선택 프로필은 별도 3 GiB 상한

전체 호스트 포트 배치는 다음과 같습니다. 컨테이너 내부 기본 포트는 바꾸지 않고 Windows 호스트에 공개되는 포트만 정렬했습니다.

| 포트 | 서비스 |
| --- | --- |
| `42200` | LIG 웹 UI |
| `42201` | RAGFlow REST API |
| `42202` | RAGFlow Admin API |
| `42203` | RAGFlow 공식 MCP |
| `42204` | Go Admin |
| `42205` | Go HTTP |
| `42206` | LIG 관리 MCP |
| `42207` | LIG 웹 HTTPS |
| `42208` | MySQL |
| `42209` | MinIO API |
| `42210` | MinIO Console |
| `42211` | Valkey/Redis |
| `42212` | Infinity Thrift |
| `42213` | Infinity HTTP |
| `42214` | Infinity PostgreSQL 호환 포트 |
| `42215` | 선택 사항인 Ollama |

`LIG-Deployment/.env.lig`는 upstream 기본값을 덮어쓰고, `LIG-Deployment/docker-compose.lig.yml`은 메모리와 로그 상한을 추가합니다. 공식 소스와 Compose는 `RAGFlow/` 아래에 원본 그대로 유지되며, 데이터는 named volume에 저장되므로 컨테이너를 다시 만들어도 유지됩니다.

## 실행

PowerShell에서 다음 명령을 사용합니다.

```powershell
cd LIG-Deployment
Copy-Item .env.secret.example .env.secret
# .env.secret의 RAGFLOW_MCP_API_KEY를 RAGFlow UI에서 만든 키로 교체
.\lig-ragflow.ps1 config
.\lig-ragflow.ps1 pull
.\lig-ragflow.ps1 build
.\lig-ragflow.ps1 start
```

RAGFlow UI에서 **설정 → 모델 공급자 → NVIDIA**를 열어 다음 임베딩 모델을 등록하고 기본 Embedding 모델로 지정합니다.

- API base: `https://integrate.api.nvidia.com/v1/embeddings`
- 모델명: `nvidia/llama-nemotron-embed-vl-1b-v2`
- 모델 유형: `Embedding`
- 최대 토큰: `10240`

NVIDIA API 키는 Compose 파일이나 저장소에 기록하지 않고 RAGFlow UI의 공급자 자격증명에만 입력합니다. NVIDIA 공개 API를 사용하려면 RAGFlow 컨테이너에서 `integrate.api.nvidia.com`으로 HTTPS 통신할 수 있어야 합니다.

NVIDIA API를 사용할 수 없는 에어갭 환경에서는 Ollama 프로필과 모델을 다음 명령으로 시작합니다.

```powershell
.\lig-ragflow.ps1 model
```

상태와 로그는 다음처럼 확인합니다.

```powershell
.\lig-ragflow.ps1 status
.\lig-ragflow.ps1 diagnostics
.\lig-ragflow.ps1 logs
```

`diagnostics`는 비밀값을 출력하지 않고 Compose 서비스 상태, Infinity·MinIO·MySQL·Valkey 상태, task executor heartbeat, 컨테이너 CPU·메모리·I/O 스냅숏, 최근 문서 처리 소요시간 로그와 오류를 JSON으로 출력합니다. heartbeat에는 최근 30분 이내 종료된 컨테이너도 남을 수 있으므로 `CurrentContainer=true`와 `CurrentTaskExecutorHeartbeatCount`를 현재 worker 수 기준으로 사용합니다. 장애나 장시간 처리 분석 시 결과를 파일로 보관할 수 있습니다.

```powershell
.\lig-ragflow.ps1 diagnostics > diagnostics.json
```

## 문서 처리 구조와 튜닝

기본 문서 등록 경로는 다음과 같습니다.

```text
업로드 → Redis 작업 큐 → RAGFlow task executor
       → 내장 DeepDoc 파서/OCR → 청킹 → 외부 임베딩 → Infinity 인덱싱
```

upstream Compose의 `deepdoc` 서비스는 선택 프로파일입니다. 현재 LIG 기본 프로파일에는 포함하지 않으며, task executor 프로세스가 RAGFlow 이미지 안의 DeepDoc 모듈을 직접 호출합니다. `DEEPDOC_URL`을 사용한 독립 서비스 운영을 검증하지 않은 상태에서 `deepdoc` 프로파일만 켜도 ingestion이 자동 분리되지는 않습니다.

`TASK_EXECUTOR_WORKERS`는 `.env.lig`에서 조정합니다. 이 배포의 기본값 2는 12개 논리 CPU와 Docker VM 메모리 15 GiB 이상을 기준으로 한 값입니다. 여러 문서 작업의 병렬 처리에는 도움이 되지만, 단일 대형 PDF의 모든 페이지를 같은 비율로 가속한다고 보장할 수 없고 worker별로 파서 모델 메모리가 중복될 수 있습니다. 메모리가 더 작은 배포 대상은 1로 낮추고, 더 늘릴 때는 실제 문서 묶음으로 처리량과 메모리를 함께 확인하십시오.

Ollama 프로필까지 동시에 실행하면 컨테이너 메모리 상한 합계가 Docker VM 할당량에 가까워집니다. 로컬 Ollama를 사용할 때는 Docker VM 메모리를 늘리거나 `TASK_EXECUTOR_WORKERS=1`로 낮춰 메모리 여유를 확보하십시오.

```dotenv
TASK_EXECUTOR_WORKERS=2
DOC_BULK_SIZE=2
EMBEDDING_BATCH_SIZE=8
```

설정 변경은 `stop` 후 `start`로 반영되며, `config`와 `start`는 worker·bulk·batch 값의 범위를 검증합니다. 초기 병목 판단 순서는 다음과 같습니다.

1. `diagnostics`의 task executor heartbeat 수가 설정값과 일치하는지 확인합니다.
2. UI의 문서 처리 상세에서 현재 단계와 실제 `process_duration`을 확인합니다.
3. 진단 결과의 `RecentStageTimings`에서 `Chunk doc`, `Indexing doc`, 전체 `Done` 소요시간을 비교합니다.
4. `ContainerStats`의 CPU·메모리·Block I/O와 `Health`의 응답시간을 함께 봅니다.

현재 v0.26.4 프런트엔드는 자체적으로 잔여시간을 계산하지 않습니다. API의 진행률, `progress_msg`, 시작 시각과 실제 경과시간을 표시하므로 “7시간” 같은 값이 보이면 해당 화면·API 응답을 먼저 확인해야 합니다. 초기 일부 페이지를 근거로 한 임의 ETA 보정 로직은 추가하지 않았습니다.

문서 유형별 권장 파서 정책은 다음과 같습니다.

| 문서 유형 | 우선 전략 |
| --- | --- |
| 텍스트 선택이 가능한 일반 PDF | 일반 파서로 시작하고 결과 품질 확인 |
| 스캔 PDF | OCR이 포함된 DeepDoc 경로 사용 |
| 표·다단 편집이 중요한 PDF | 레이아웃·표 분석을 켜고 샘플 품질/시간 비교 |
| 복잡한 보고서·논문 | Docling/MinerU를 별도 검증한 후 데이터셋 단위 선택 |
| 이미지·도면 의미 분석 | VLM을 명시적으로 등록하고 필요한 데이터셋에만 적용 |

파서나 embedding 모델을 바꾸면 기존 벡터와 새 벡터를 섞지 마십시오. embedding 차원과 의미 공간이 달라질 수 있으므로 해당 데이터셋은 재인덱싱하거나 새 데이터셋으로 검증해야 합니다.

이 배포는 Infinity를 사용하므로 Elasticsearch heap/health 명령은 적용 대상이 아닙니다. 외부 NVIDIA embedding은 온라인 환경용이고, 폐쇄망에서는 내부 vLLM의 생성 모델과 별개로 Ollama 또는 사내 OpenAI 호환 embedding endpoint를 등록합니다. 생성 LLM과 embedding 모델의 역할은 서로 대체되지 않습니다.

`stop`은 컨테이너와 네트워크만 제거하며 데이터 볼륨은 삭제하지 않습니다.

```powershell
.\lig-ragflow.ps1 stop
```

## 디스크 기준

공식 50 GB 권장은 이미지, 검색 엔진, 모델, 문서 증가분까지 여유 있게 포함한 운영 기준입니다. 이 프로필은 Elasticsearch와 로컬 TEI 모델을 제외하고 로그를 순환시켜 초기 설치와 소규모 문서 시험을 25 GB 이내로 유지하는 것을 목표로 합니다. 스크립트는 pull/start 전에 C 드라이브 여유 공간 20 GiB를 검사합니다. 문서 원본, 파싱 결과, 인덱스는 계속 증가하므로 `lig-ragflow.ps1 status`의 Docker 사용량을 정기적으로 확인해야 합니다.

Windows의 Docker VHDX는 내부 데이터를 지워도 파일 크기가 즉시 줄지 않습니다. 실제 C 드라이브 공간 회수에는 Docker 종료 후 관리자 권한으로 VHDX 최적화가 별도로 필요합니다.

## 모델과 에어갭

온라인 환경의 기본 구성은 NVIDIA 공개 API의 `nvidia/llama-nemotron-embed-vl-1b-v2`를 사용하므로 로컬 임베딩 모델 메모리가 필요하지 않습니다. RAGFlow의 NVIDIA 드라이버는 문서 인덱싱에는 `input_type=passage`, 검색 질의에는 `input_type=query`를 사용하고 긴 입력은 끝부분을 잘라 요청합니다.

RAGFlow `v0.22` 이후 기본 이미지는 임베딩 모델을 포함하지 않습니다. 에어갭 대체 구성은 Ollama와 다국어 `qwen3-embedding:0.6b`를 사용합니다. Ollama 모델은 약 639 MB이고 100개 이상 언어 및 32K 문맥을 지원해 한국어 문서 시험에 적합합니다. 16 GB 노트북에는 공식 TEI 기본 Qwen3 0.6B(약 25 GB RAM 요구)나 BGE-M3(약 21 GB)가 맞지 않아 TEI는 제외했습니다.

에어갭 반입 시에는 compose에 사용되는 모든 Docker 이미지를 인터넷 환경에서 내보내 gzip으로 압축하고, 폐쇄망에서 Docker가 압축 아카이브를 직접 복원합니다. 기본 내보내기에는 LIG UI 이미지와 공식 롤백 이미지가 모두 포함되며 Ollama는 포함하지 않습니다.

온라인 PC에서 반입 묶음을 만드는 명령은 다음과 같습니다. 결과 폴더에는 커스텀 UI와 LIG 관리 MCP를 포함한 고정 버전 이미지, 공식 Compose 런타임, 운영 스크립트와 SHA-256 manifest가 생성됩니다. 원본 Git 저장소는 폐쇄망 PC에 필요하지 않습니다. `.env.secret`은 보안상 묶음에 포함하지 않고 예제 파일만 제공합니다.
내보내기 대상은 기존 파일이나 비밀값이 섞이지 않은 빈 폴더여야 합니다.

```powershell
.\airgap-export.ps1 -Destination D:\LIG-RAGFlow-Airgap
```

생성된 `D:\LIG-RAGFlow-Airgap` 폴더 전체를 폐쇄망 PC로 복사한 후 Docker Desktop을 시작하고 다음 한 줄로 설치합니다.

```powershell
cd D:\LIG-RAGFlow-Airgap
.\install.ps1
```

이후에는 같은 폴더의 `start.ps1`, `stop.ps1`, `status.ps1`, `logs.ps1`로 운영합니다.

폐쇄망 내부 vLLM을 사용할 때는 RAGFlow에 vLLM의 OpenAI 호환 base URL과 모델명을 등록합니다. vLLM이 Docker 호스트에서 실행되면 `http://host.docker.internal:<port>/v1`, 별도 폐쇄망 서버라면 `http://<internal-vllm-host>:<port>/v1` 형태를 사용합니다. RAGFlow 컨테이너 내부의 `127.0.0.1`은 vLLM 호스트가 아니므로 base URL로 사용하지 않습니다.

Ollama 모델까지 반입할 경우에만 다음처럼 선택 옵션을 사용합니다. 이때 `lig-ragflow-ollama-1` 컨테이너에 모델이 미리 설치되어 있어야 합니다.

```powershell
.\airgap-export.ps1 -Destination D:\LIG-RAGFlow-Airgap -IncludeOllama
```

## MCP 범위

RAGFlow 기본 MCP는 검색과 데이터셋·채팅 목록 조회에 집중합니다. 이 Compose는 공식 MCP `http://127.0.0.1:42203/mcp`와 LIG 관리 MCP `http://127.0.0.1:42206/mcp`를 RAGFlow와 함께 시작합니다. 관리 MCP는 데이터셋·문서와 나머지 `/api/v1` 운영 기능을 제공하며, 요청에는 `.env.secret`의 `RAGFLOW_MCP_API_KEY`를 Bearer 키로 사용합니다.

컨테이너 MCP가 읽을 파일은 `LIG-Deployment/mcp-files`에 넣고 도구 인수에는 `/data/<파일명>`을 전달합니다. 이 폴더는 Compose에서 관리 MCP 컨테이너에만 연결됩니다.
