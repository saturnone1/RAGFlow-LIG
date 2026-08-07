# LIG RAGFlow 경량 배포

이 구성은 공식 RAGFlow `v0.26.4`를 수정하지 않고 Windows 노트북과 에어갭 환경에서 관리하기 위한 오버레이입니다. 특정 PDF에 종속되지 않으며, 문서 저장·파싱·청킹·검색은 RAGFlow가 담당합니다.

## 선택한 구성

- 문서 엔진: Elasticsearch 대신 Infinity
- 실행 장치: 로컬 기본 CPU, 에어갭 번들은 NVIDIA DeepDoc GPU 설치도 지원
- GPU 런타임: CPU 이미지와 분리한 CUDA 12.8·cuDNN 9 전용 RAGFlow/PaddleOCR 이미지
- 한국어 OCR: CPU/GPU 프로필에 `korean_PP-OCRv5_mobile_rec` 모델을 포함한 내부 PaddleOCR 서비스 자동 실행
- 내부 서비스: RAGFlow, 한국어 PaddleOCR, LIG 관리 MCP, Infinity, MySQL, MinIO, Valkey
- 온라인 임베딩 선택지: NVIDIA 공개 API의 `nvidia/llama-nemotron-embed-vl-1b-v2`
- 선택 설치 임베딩: TEI CPU 기반 `Qwen/Qwen3-Embedding-0.6B`(1024차원, 모델과 런타임을 별도 에어갭 아카이브에 포함)
- 제외: Kibana, Sandbox, 별도 Docling 서비스
- 포트: 모두 `127.0.0.1`에만 공개
- 포트 블록: 다른 로컬 MCP 서버와 분리한 `42300`~`42317`
- 웹 UI: `http://127.0.0.1:42300`
- REST API: `http://127.0.0.1:42301`
- 공식 MCP: `http://127.0.0.1:42303/mcp`
- LIG 관리 MCP: `http://127.0.0.1:42306/mcp`
- 한국어 PaddleOCR 상태: `http://127.0.0.1:42316/health`
- 선택형 Qwen3 임베딩 상태: `http://127.0.0.1:42317/health`
- 로그: 컨테이너마다 최대 20 MiB 파일 3개
- 동시 처리: CPU·GPU 모두 기본 task executor 1개. 작업은 거부하지 않고 대기시키며, 실제 메모리 여유를 확인한 뒤에만 worker 수를 늘림
- 취소·장애 복구: 협력 가능한 파서는 즉시 중단하고, 네이티브/외부 파서가 취소를 무시하면 격리된 task executor 프로세스만 5초 후 재기동합니다. 컨테이너 교체로 이전 consumer에 남은 Redis pending 메시지는 5분 유휴 후 현재 worker가 자동 인계하며, 갱신형 task lease로 중복 실행을 막습니다.
- 자원: Compose에서 컨테이너별 CPU·시스템 RAM 상한을 두지 않으며, upstream Infinity의 RAM 상한도 LIG 오버레이에서 해제. Docker Engine 또는 서버 운영 정책의 전체 자원 범위를 사용

전체 호스트 포트 배치는 다음과 같습니다. 컨테이너 내부 기본 포트는 바꾸지 않고 Windows 호스트에 공개되는 포트만 정렬했습니다.

| 포트 | 서비스 |
| --- | --- |
| `42300` | LIG 웹 UI |
| `42301` | RAGFlow REST API |
| `42302` | RAGFlow Admin API |
| `42303` | RAGFlow 공식 MCP |
| `42304` | Go Admin |
| `42305` | Go HTTP |
| `42306` | LIG 관리 MCP |
| `42307` | LIG 웹 HTTPS |
| `42308` | MySQL |
| `42309` | MinIO API |
| `42310` | MinIO Console |
| `42311` | Valkey/Redis |
| `42312` | Infinity Thrift |
| `42313` | Infinity HTTP |
| `42314` | Infinity PostgreSQL 호환 포트 |
| `42316` | 한국어 PaddleOCR API |
| `42317` | 선택형 Qwen3 임베딩 API |

`LIG-Deployment/.env.lig`는 upstream 기본값을 덮어쓰고, `LIG-Deployment/docker-compose.lig.yml`은 로그 크기 상한과 LIG 서비스 구성을 추가합니다. 문서 암호 처리와 OCR/청킹 보강이 적용된 경로를 기본 사용하도록 `API_PROXY_SCHEME=python`을 설정합니다. upstream의 Go/Hybrid 모드를 명시적으로 선택하는 기능은 막지 않지만, 그 경로에서는 LIG 문서 암호와 OCR 보강 전체가 적용되지 않습니다. 컨테이너별 CPU·시스템 RAM 상한은 두지 않습니다. 로그 회전 상한은 디스크 고갈 방지 설정이므로 유지합니다. 공식 소스와 Compose는 `RAGFlow/` 아래에 원본 그대로 유지되며, 데이터는 named volume에 저장되므로 컨테이너를 다시 만들어도 유지됩니다.

## 실행

PowerShell에서 다음 명령을 사용합니다.

```powershell
cd LIG-Deployment
Copy-Item .env.secret.example .env.secret
# .env.secret의 RAGFLOW_MCP_API_KEY를 RAGFlow UI에서 만든 키로 교체
.\lig-ragflow.ps1 config
.\lig-ragflow.ps1 pull
.\lig-ragflow.ps1 build
.\verify-cpu-images.ps1
.\lig-ragflow.ps1 start
```

`verify-cpu-images.ps1`은 별도 테스트 패키지를 설치하지 않고 빌드된 이미지 안에서 암호 PDF의 실제 본문 보존, 일반 문서의 잔존 암호 제거, 청킹 방식 변경 시 봉인 암호 승계, OCR/청킹 런타임 패치 포함, 한국어 PP-OCRv5 모델 메타데이터와 대형 페이지 축소 계산, MCP .NET 런타임을 검사합니다.

NVIDIA GPU 실행 이미지는 CPU 이미지 위에 고정된 CUDA 12.8·cuDNN 9 라이브러리를 추가합니다. GPU 장비 또는 CPU/GPU 에어갭 번들을 만들 PC에서는 기본 빌드 후 다음 명령도 실행합니다.

```powershell
.\lig-ragflow.ps1 gpu-build
```

RAGFlow UI에서 **설정 → 모델 공급자 → NVIDIA**를 열어 다음 임베딩 모델을 등록하고 기본 Embedding 모델로 지정합니다.

- API base: `https://integrate.api.nvidia.com/v1/embeddings`
- 모델명: `nvidia/llama-nemotron-embed-vl-1b-v2`
- 모델 유형: `Embedding`
- 최대 토큰: `10240`

NVIDIA API 키는 Compose 파일이나 저장소에 기록하지 않고 RAGFlow UI의 공급자 자격증명에만 입력합니다. NVIDIA 공개 API를 사용하려면 RAGFlow 컨테이너에서 `integrate.api.nvidia.com`으로 HTTPS 통신할 수 있어야 합니다.

로컬 Qwen3 임베딩은 기본 설치와 별도로 다음 명령으로 빌드하고 시작합니다. 기본 `start`는 이 선택 서비스를 자동으로 추가하지 않습니다.

```powershell
.\lig-ragflow.ps1 embedding-build
.\lig-ragflow.ps1 embedding-start
.\lig-ragflow.ps1 embedding-test
```

RAGFlow에는 공급자 `HuggingFace`, 모델명 `Qwen/Qwen3-Embedding-0.6B`, Base URL `http://qwen3-embedding:8080`, 유형 `Embedding`, 최대 토큰 `2048`로 등록합니다. Docker 호스트에서 직접 시험할 때만 `http://127.0.0.1:42317`을 사용합니다. CPU 추론의 공급자 요청 제한시간은 300초이며 `.env.lig`의 `EMBEDDING_BATCH_SIZE=4`를 사용합니다. 임베딩 처리량은 이 값이 아니라 `MAX_CONCURRENT_EMBEDDERS=4`가 결정합니다. 12코어 호스트에서 순차 실행 대비 7.3배 빨랐습니다. `EMBEDDING_BATCH_SIZE`와 `qwen3-embedding-tei`의 `--max-batch-tokens 2048`은 올려도 처리량이 늘지 않고 기동 시 메모리만 커집니다(2048에서 3.3GB, 8192에서 15.3GB). 그대로 두십시오. `EMBEDDING_MAX_CONCURRENT_REQUESTS=4`는 어댑터가 문서 처리와 사용자 검색 질의를 동시에 넘길 수 있게 해 검색이 처리 중인 배치 뒤에서 대기하지 않게 하고, `HUGGINGFACE_EMBEDDING_MAX_RETRIES=0`은 문서 처리 중 일시적인 TEI 재기동에도 제한 횟수 없이 재연결합니다. 대화 검색은 `HUGGINGFACE_EMBEDDING_QUERY_MAX_RETRIES=3`으로 무한 대기하지 않고 명시적인 장애를 반환합니다. 이 값들은 CPU·RAM 사용량이나 문서 전체 크기의 상한이 아닙니다.

상태와 로그는 다음처럼 확인합니다.

```powershell
.\lig-ragflow.ps1 status
.\lig-ragflow.ps1 diagnostics
.\lig-ragflow.ps1 logs
```

`diagnostics`는 비밀값을 출력하지 않고 UI·API·두 MCP의 정확한 주소와 MCP initialize 결과, Compose 서비스 상태, Infinity·MinIO·MySQL·Valkey 상태, task executor heartbeat, 컨테이너 CPU·메모리·I/O 스냅숏, 최근 문서 처리 소요시간 로그와 오류를 JSON으로 출력합니다. heartbeat의 `GroupPending`은 consumer group 전체의 미승인 작업 수이고 `GroupLag`는 아직 어느 worker에도 전달되지 않은 작업 수입니다. 최근 30분 이내 종료된 컨테이너도 남을 수 있으므로 `CurrentContainer=true`와 `CurrentTaskExecutorHeartbeatCount`를 현재 worker 수 기준으로 사용합니다. 장애나 장시간 처리 분석 시 결과를 파일로 보관할 수 있습니다.

```powershell
.\lig-ragflow.ps1 diagnostics > diagnostics.json
```

## 문서 처리 구조와 튜닝

지원 확장자×청킹 방식의 전체 표, HWP/HWPX 변환 손실, 파일 열기 암호 제외 범위와 키 회전·복구 절차는 [DOCUMENT-COMPATIBILITY.ko.md](DOCUMENT-COMPATIBILITY.ko.md)를 기준으로 합니다.

기본 문서 등록 경로는 다음과 같습니다.

```text
업로드 → Redis 작업 큐 → RAGFlow task executor
       → 내장 DeepDoc 파서/OCR → 청킹 → 외부 임베딩 → Infinity 인덱싱
```

upstream Compose의 `deepdoc` 서비스는 선택 프로파일입니다. 현재 LIG 기본 프로파일에는 포함하지 않으며, task executor 프로세스가 RAGFlow 이미지 안의 DeepDoc 모듈을 직접 호출합니다. `DEEPDOC_URL`을 사용한 독립 서비스 운영을 검증하지 않은 상태에서 `deepdoc` 프로파일만 켜도 ingestion이 자동 분리되지는 않습니다.

한국어 스캔 PDF에는 별도 `paddleocr-cpu` 또는 `paddleocr-gpu` 서비스가 자동 실행됩니다. 이 서비스는 한국어·영어·숫자를 지원하는 PP-OCRv5 한국어 모델을 이미지에 선탑재하므로 에어갭에서도 추가 다운로드가 없습니다. 업로드 원본과 페이지별 JSONL 결과는 임시 디스크에 순차 기록하고 작업 만료 후 삭제하므로 대형 PDF 전체를 Python 메모리에 유지하지 않습니다. 데이터셋 언어를 `Korean`, 청킹 방식을 `Naive`, PDF 파서를 `paddleocr-from-env`로 선택하십시오. RAGFlow는 PDF를 `PADDLEOCR_TASK_PAGE_SIZE` 단위의 작업으로 나누고, 각 작업은 해당 페이지만 새 PDF로 구성해 OCR 서비스에 전송하므로 전체 원본을 작업마다 반복 처리하지 않습니다. 내부 API URL, 토큰과 `PP-OCRv5`는 자동 적용되며 데이터셋 화면에서 별도로 입력하지 않습니다. 텍스트 선택과 복사가 정상인 PDF는 OCR 없이 `Plain Text`가 더 빠르고 정확합니다.

**파일 열기 암호**를 설정한 PDF, Word(`.docx`/`.doc`), Excel(`.xlsx`/`.xls`), PowerPoint(`.pptx`/`.ppt`) 및 HWPX는 업로드 창에서 파일별 비밀번호를 입력할 수 있습니다. 업로드 단계에서 암호를 검증한 뒤 원본 암호화 문서는 그대로 저장하고, 비밀번호는 `.env.secret`의 `LIG_DOCUMENT_PASSWORD_KEY`로 AES-256-GCM 암호화해 문서 설정에 보관합니다. 작업자는 파싱 직전에 메모리에서 문서를 복호화해 기존 파서로 전달합니다. HWPX는 한컴의 AES-256-CBC/PBKDF2 형식을 복호화하고 XML 본문을 텍스트로 변환하며, 일반 HWP 5와 HWPX도 텍스트 문서로 처리합니다. 잘못된 암호는 업로드 오류로 바로 표시되며, 문서의 청킹 방식 설정에서 새 암호를 저장하고 재실행할 수도 있습니다.

암호 PDF 처리 기록이 `OCR started`까지 진행됐다면 입력한 파일 열기 암호는 이미 검증된 것입니다. 권한 제한 PDF에 소유자 암호가 필요한 경우에는 OCR 전에 별도 오류로 중단됩니다. 현재 이미지는 Adobe 계열 암호 PDF를 복호화할 때 암호화된 문서 카탈로그를 복제하지 않고 각 페이지를 새 비암호 PDF로 재구성하여, 페이지 수만 남고 OCR 본문이 비는 문제를 방지합니다.

암호화된 바이너리 HWP는 검증된 공개 복호화 구현이 없어 현재 명시적으로 거부하며 HWPX 또는 DOCX로 다시 저장해야 합니다. HWP 배포용 문서, PDF 권한 제한, Office 편집·시트 보호처럼 열람이 아니라 사용 권한을 제한하는 문서는 우회하지 않습니다. Microsoft IRM/MIP/AIP, FASOO 등 계정·인증서·권한 서버 기반 DRM도 대상이 아닙니다. 레거시 `.xls`와 `.ppt`의 오래된 암호 규격은 복호화 라이브러리의 실험적·부분 지원 범위에 따라 거부될 수 있습니다.

`LIG_DOCUMENT_PASSWORD_KEY`는 최초 `config`/`start` 또는 에어갭 반입 때 자동 생성됩니다. 기존 `LIG_PDF_PASSWORD_KEY`가 있으면 같은 키 값을 새 이름으로 자동 이전하여 저장된 PDF 암호를 계속 사용할 수 있습니다. 이 값을 잃거나 바꾸면 기존에 저장한 문서 비밀번호를 해제할 수 없으므로 `.env.secret`을 운영 백업에 포함하되 Git이나 에어갭 배포 묶음에는 넣지 마십시오. 비밀번호 평문과 내부 암호문은 API 응답 및 진단 출력에 포함되지 않습니다. 운영 중 키는 `rotate-document-password-key.ps1 audit|rotate`로 감사·회전하며, 회전 전 백업과 DB를 같은 복구 시점으로 관리합니다.

DeepDOC는 삭제하지 않습니다. DeepDOC는 OCR뿐 아니라 레이아웃, 표, 좌표와 이미지 영역을 처리하며 영어·중국어 문서 및 복잡한 편집 문서에서 여전히 별도 가치가 있습니다. 한국어 스캔 문서에서는 DeepDOC 문자 사전에 한글이 없어 PaddleOCR를 사용합니다.

API와 문서 작업기는 별도 컨테이너로 실행됩니다. 문서 작업기가 재시작되어도 웹/API와 데이터베이스가 함께 내려가지 않으며, 동일 작업에는 Redis lease를 사용해 중복 OCR을 막습니다. `TASK_EXECUTOR_WORKERS`의 초기값은 1입니다. 여러 문서의 병렬 처리가 반드시 필요하고 실제 메모리 여유를 확인한 경우에만 늘리십시오. worker마다 파서 모델 메모리가 중복됩니다.

선택형 Qwen3 TEI CPU 서비스는 현재 설정에서 유휴 메모리 약 1.5 GiB를 추가로 사용합니다. Docker VM 메모리가 부족하면 `TASK_EXECUTOR_WORKERS=1`로 낮추거나 임베딩 서비스를 별도 서버에서 운영하십시오. Compose는 시스템 RAM 상한을 강제로 설정하지 않습니다.

```dotenv
TASK_EXECUTOR_WORKERS=1
```

문서 bulk와 thread pool은 RAGFlow upstream 기본값을 사용합니다. 로컬 Qwen3 CPU 경로의 공급자 요청 제한시간은 300초이고 embedding batch는 4입니다. 요청 단위 조정이며 자원 상한은 아닙니다. 설정 변경은 `stop` 후 `start`로 반영되며, `config`와 `start`가 값을 검증합니다. 초기 병목 판단 순서는 다음과 같습니다.

내부 PaddleOCR의 문서 크기와 페이지 수는 기본적으로 제한하지 않습니다. RAGFlow는 PDF를 최대 12쪽 작업으로 나누고, 그보다 메모리가 부족하면 현재 가용 메모리·worker 수·파서 동시성에 맞춰 작업 페이지 수를 1쪽까지 자동 축소합니다. OCR 서비스도 페이지를 한 장씩 렌더링하고 메모리가 부족하면 회수될 때까지 대기합니다. 큰 페이지는 현재 메모리 예산에 맞게 축소하고, OCR 큐가 차면 거부하지 않고 순서를 기다립니다. `MAX_CONTENT_LENGTH`, `LIG_DOCUMENT_MAX_BYTES`, `PADDLEOCR_MAX_UPLOAD_BYTES`, `PADDLEOCR_MAX_PDF_PAGES`의 `0`은 무제한입니다. 완료·실패 결과만 TTL 후 삭제하고 실행 중 작업은 정리하지 않습니다. 내부 Bearer 토큰과 문서 암호화 키는 최초 실행 때 생성해 `%LOCALAPPDATA%\LIG-RAGFlow\.env.secret`에도 보존하므로 새 번들 폴더로 교체해도 기존 DB의 저장 암호를 계속 해제할 수 있습니다.

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

이 배포는 Infinity를 사용하므로 Elasticsearch heap/health 명령은 적용 대상이 아닙니다. 외부 NVIDIA embedding은 온라인 환경용이고, 폐쇄망에서는 번들의 선택형 Qwen3 TEI 또는 사내 embedding endpoint를 등록합니다. 생성 LLM과 embedding 모델의 역할은 서로 대체되지 않습니다.

`stop`은 컨테이너와 네트워크만 제거하며 데이터 볼륨은 삭제하지 않습니다.

```powershell
.\lig-ragflow.ps1 stop
```

## 디스크 기준

공식 50 GB 권장은 이미지, 검색 엔진, 모델, 문서 증가분까지 여유 있게 포함한 운영 기준입니다. 기본 RAGFlow 설치와 선택형 Qwen3 이미지 아카이브는 분리되어 있으며, Qwen3 모델 이미지는 로컬 Docker에 약 1.18 GB를 추가합니다. 스크립트는 pull/start 전에 C 드라이브 여유 공간 20 GiB를 검사합니다. 문서 원본, 파싱 결과, 인덱스는 계속 증가하므로 `lig-ragflow.ps1 status`의 Docker 사용량을 정기적으로 확인해야 합니다.

Windows의 Docker VHDX는 내부 데이터를 지워도 파일 크기가 즉시 줄지 않습니다. 실제 C 드라이브 공간 회수에는 Docker 종료 후 관리자 권한으로 VHDX 최적화가 별도로 필요합니다.

## 모델과 에어갭

온라인 환경의 기본 구성은 NVIDIA 공개 API의 `nvidia/llama-nemotron-embed-vl-1b-v2`를 사용하므로 로컬 임베딩 모델 메모리가 필요하지 않습니다. RAGFlow의 NVIDIA 드라이버는 문서 인덱싱에는 `input_type=passage`, 검색 질의에는 `input_type=query`를 사용하고 긴 입력은 끝부분을 잘라 요청합니다.

RAGFlow 기본 이미지는 임베딩 모델을 포함하지 않습니다. 이 배포는 Apache-2.0의 `Qwen/Qwen3-Embedding-0.6B`를 커밋 `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`으로 고정하고 TEI `cpu-1.9` 이미지에 포함합니다. 모델은 100개 이상 언어와 1024차원 벡터를 지원합니다. 운영 설정은 RAGFlow 청크 처리에 맞춰 요청당 최대 2,048 토큰으로 자동 절단하며, 검색 질의에만 Qwen 권장 instruction을 붙이고 문서 청크는 원문 그대로 임베딩합니다.

에어갭 반입 폴더의 기본 런타임 아카이브에는 CPU 이미지가 들어갑니다. CUDA 12.8 GPU 이미지는 `-IncludeGpu`, Qwen3 임베딩 아카이브는 `-IncludeEmbedding`을 지정한 경우에만 추가됩니다. 각 선택 이미지를 포함한 번들에서만 `install-gpu.ps1` 또는 `install-embedding-cpu.ps1`을 사용할 수 있습니다.

온라인 PC에서 먼저 `build`를 완료한 뒤 반입 묶음을 만듭니다. GPU를 동봉할 때만 `gpu-build`와 `-IncludeGpu`, 임베딩을 동봉할 때만 `embedding-build`와 `-IncludeEmbedding`이 필요합니다. 결과 폴더에는 선택한 고정 버전 이미지, 공식 Compose 런타임, 문서 호환성·키 회전 자료, 운영 스크립트와 SHA-256 manifest가 생성됩니다. 원본 Git 저장소는 폐쇄망 PC에 필요하지 않습니다. `.env.secret`은 보안상 묶음에 포함하지 않고 예제 파일만 제공합니다.
내보내기 대상은 기존 파일이나 비밀값이 섞이지 않은 빈 폴더여야 합니다.

```powershell
.\airgap-export.ps1 -Destination D:\LIG-RAGFlow-Airgap -IncludeEmbedding
```

생성된 `D:\LIG-RAGFlow-Airgap` 폴더 전체를 폐쇄망 PC로 복사한 후 Docker Desktop을 시작하고 다음 한 줄로 설치합니다.

```powershell
cd D:\LIG-RAGFlow-Airgap
.\install.ps1
```

NVIDIA GPU 장비에는 다음 설치 스크립트를 사용합니다. CUDA 접근이 확인되지 않으면 설치가 즉시 실패합니다.

```powershell
.\install-gpu.ps1
```

이후 CPU 장비는 `start.ps1`, GPU 장비는 `start-gpu.ps1`로 시작합니다. GPU 진단은 `diagnostics-gpu.ps1`을 사용합니다.

폐쇄망 장비에 사내 임베딩 서버가 없다면 기본 설치 후 다음 스크립트를 한 번 더 실행합니다. 이후 재부팅 시 컨테이너의 `unless-stopped` 정책으로 자동 시작되며, 수동 시작·중지·검증 스크립트도 함께 제공됩니다.

```powershell
.\install-embedding-cpu.ps1
.\test-embedding.ps1
```

폐쇄망 내부 vLLM을 사용할 때는 RAGFlow에 vLLM의 OpenAI 호환 base URL과 모델명을 등록합니다. vLLM이 Docker 호스트에서 실행되면 `http://host.docker.internal:<port>/v1`, 별도 폐쇄망 서버라면 `http://<internal-vllm-host>:<port>/v1` 형태를 사용합니다. RAGFlow 컨테이너 내부의 `127.0.0.1`은 vLLM 호스트가 아니므로 base URL로 사용하지 않습니다.

## MCP 범위

RAGFlow 기본 MCP는 검색과 데이터셋·채팅 목록 조회에 집중합니다. 이 Compose는 공식 MCP `http://127.0.0.1:42303/mcp`와 LIG 관리 MCP `http://127.0.0.1:42306/mcp`를 RAGFlow와 함께 시작합니다. 관리 MCP는 데이터셋·문서와 나머지 `/api/v1` 운영 기능을 제공하며, 요청에는 `.env.secret`의 `RAGFLOW_MCP_API_KEY`를 Bearer 키로 사용합니다.

`9382`는 RAGFlow 컨테이너 내부 MCP 포트이며 이 배포의 Windows 호스트 접속 포트가 아닙니다. REST API는 `http://127.0.0.1:42301/api/v1/...`에 호출합니다. `42300`은 웹 UI이므로 `http://127.0.0.1:42300/api/v1/chat` 같은 호출은 404가 정상이며, RAGFlow에는 범용 `/api/v1/chat` 단일 엔드포인트가 없습니다. MCP 클라이언트에는 REST API 주소가 아니라 위 `/mcp` 주소를 등록하십시오.

컨테이너 MCP가 읽을 파일은 `LIG-Deployment/mcp-files`에 넣고 도구 인수에는 `/data/<파일명>`을 전달합니다. 이 폴더는 Compose에서 관리 MCP 컨테이너에만 연결됩니다.
