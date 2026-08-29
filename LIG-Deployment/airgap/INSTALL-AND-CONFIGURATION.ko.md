# LIG AI Knowledge Hub 설치 및 환경설정 설명서

이 설명서는 인터넷이 차단된 Windows PC에 번들을 설치하고, 사내 vLLM과 MCP를 연결하는 절차를 다룹니다. 번들에는 Docker 이미지와 고정된 Compose 파일이 들어 있으므로 대상 PC에 Git 저장소나 Node.js, Python SDK가 필요하지 않습니다.

## 1. 설치 전 준비

- Windows 10/11 64비트
- Docker Desktop과 Docker Compose v2
- C 드라이브 여유 공간 20 GiB 이상
- 호스트 포트 `42300`~`42317`이 비어 있어야 함
- 사내 생성 LLM과 embedding 모델을 사용할 경우 해당 서버의 IP, 포트, 모델명, API 키

NVIDIA DeepDoc GPU 설치에는 다음 조건이 추가로 필요합니다.

- CUDA를 지원하는 NVIDIA GPU와 최신 드라이버
- Docker Desktop의 Linux 컨테이너에서 NVIDIA GPU 접근 가능
- GPU VRAM 12 GiB 이상 권장
- 호스트 RAM 32 GiB 이상, Docker에 20~24 GiB 메모리 할당 권장

Docker Desktop에서 Linux containers 모드를 사용하고 PowerShell을 일반 사용자 권한으로 실행합니다. 번들 폴더의 파일명과 구조는 변경하지 마십시오. `manifest.json`이 모든 파일의 크기와 SHA-256을 검증합니다.

## 2. 최초 설치

번들 전체를 대상 PC의 로컬 디스크로 복사한 후 PowerShell에서 실행합니다.

```powershell
cd D:\LIG-RAGFlow-Airgap-20260728
# CPU DeepDoc 설치
.\install.ps1

# 또는 NVIDIA GPU DeepDoc 설치
# (-IncludeGpu로 생성한 번들에서만 가능)
.\install-gpu.ps1
```

설치 프로그램은 다음 작업을 자동 수행합니다.

1. manifest와 모든 파일의 SHA-256 검증
2. RAGFlow 기본 Docker 이미지와 번들 생성 시 선택한 DeepDOC GPU 이미지가 포함된 gzip 아카이브 로드
3. `.env.secret` 예제 생성
4. 로그와 MCP 파일 교환 폴더 생성
5. RAGFlow, Infinity, MySQL, MinIO, Valkey, 공식 MCP, LIG 관리 MCP 시작

`install-gpu.ps1`은 CPU 이미지와 분리된 CUDA 12.8·cuDNN 9 RAGFlow 이미지를 사용합니다. 이미지 로드 후 임시 컨테이너에서 GPU 이름과 VRAM, `libcublasLt.so.12` 로딩과 DeepDOC CUDA 세션 생성을 검증합니다. 검증 실패 시 CPU 모드로 대체하지 않고 설치를 중단합니다.

CPU·GPU 기본 설치에는 OCR 모델이 포함되지 않습니다. 한국어 PP-OCRv5 추가 패키지는 `CPUExecutionProvider`만 사용하며, GPU 설치의 NVIDIA 장치는 DeepDOC와 선택형 PaddleOCR-VL VLM에만 사용합니다. 선택 패키지의 모델은 해당 이미지에 포함되어 폐쇄망에서 추가 다운로드하지 않습니다.

데이터셋 화면에서 저장한 파서/OCR 모델 설정은 공유 DB의 데이터셋과 기존 문서에 함께 반영되어 모든 작업 컨테이너가 같은 값을 읽습니다. 대기 중 작업은 새 설정으로 실행되고, 이미 실행 중인 작업만 결과 일관성을 위해 시작 시점 설정을 유지합니다. UI에서 수정한 모델 URL·토큰·알고리즘·API 방식은 컨테이너 환경변수가 다시 덮어쓰지 않습니다. 사내 원격 PaddleX API는 `API 방식=PaddleX Image API`로 지정하고, 번들 내부 OCR은 `자동` 또는 `RAGFlow Job API`를 사용합니다. Infinity는 CPU·시스템 메모리 상한 없이 실행하며 설치 전 구성 검사가 이를 확인합니다. 서비스 실행기는 회사 보안 정책에 맞춰 Bash 문자열 명령과 `eval`을 사용하지 않습니다.

완료 후 설치 PC에서는 `http://127.0.0.1:42300`, 같은 사내망의 다른 PC에서는 `http://<RAG-PC-IP>:42300`에 접속합니다. 최초 관리자 계정을 만든 뒤 각 사용자는 가입 화면에서 자신의 사내 계정을 생성하고 개인 설정 API 메뉴에서 개인 API 키를 발급합니다.

## 3. 운영 명령

```powershell
# CPU 설치 장비
.\start.ps1

# GPU 설치 장비
.\start-gpu.ps1

.\stop.ps1
.\status.ps1
.\diagnostics.ps1
.\diagnostics-gpu.ps1
.\recovery-test.ps1
.\logs.ps1
```

- `start.ps1`: 기존 데이터 볼륨을 유지하며 서비스 시작
- `start-gpu.ps1`: NVIDIA DeepDoc GPU 프로필과 `.env.lig`에 지정한 executor 수로 시작. 12 GiB는 GPU VRAM 기준이며 CPU·시스템 RAM 상한을 설정하지 않음
- `install-embedding-cpu.ps1`: 별도 Qwen3 이미지 아카이브를 검증·로드하고 CPU 임베딩 서비스 시작
- `install-paddleocr.ps1`: 별도 한국어 PP-OCRv5 이미지 아카이브를 검증·로드하고 CPU OCR 서비스 시작
- `start-embedding-cpu.ps1` / `stop-embedding.ps1`: 선택형 임베딩 서비스만 시작 또는 중지
- `test-embedding.ps1`: health와 한국어·영어 1024차원 배치 추론 검증
- `start-paddleocr.ps1` / `stop-paddleocr.ps1`: 선택형 일반 PP-OCRv5 CPU 서비스만 시작 또는 중지
- `test-paddleocr.ps1`: 일반 PaddleOCR 컨테이너 health 검증
- `stop.ps1`: 기본 서비스와 선택 실행한 PaddleOCR·PaddleOCR-VL·embedding 컨테이너 및 네트워크를 모두 중지·제거하며 문서 데이터는 삭제하지 않음
- `status.ps1`: 컨테이너와 Docker 디스크 사용량 확인
- `diagnostics.ps1`: 의존성 health, Redis 큐 길이·pending·lag, 현재 task executor, 자원 사용량, 최근 처리시간과 오류를 JSON으로 출력
- `diagnostics-gpu.ps1`: GPU 프로필을 기준으로 같은 진단 실행
- `recovery-test.ps1`: one-shot DB migration 상태를 확인하고 worker·Infinity 재시작 복구와 API health를 시험. 실행 중 처리는 잠시 중단됨
- `backup.ps1`: 서비스를 정지해 네 named volume과 환경 파일을 같은 시점으로 백업하고 SHA-256 manifest 생성
- `restore.ps1`: manifest를 먼저 검증한 뒤 `-ConfirmRestore`가 있을 때만 기존 볼륨 내용을 복원
- `logs.ps1`: 최근 컨테이너 로그 출력
- 한국어 PaddleOCR 상태: `http://127.0.0.1:42316/health`

진단 결과를 파일로 보관하려면 다음과 같이 실행합니다.

```powershell
.\diagnostics.ps1 > diagnostics.json
```

## 4. 포트

웹 UI `42300`, REST API `42301`, 공식 MCP `42303`, LIG 관리 MCP `42306`과 웹 HTTPS `42307`은 `0.0.0.0`에 바인딩됩니다. DB·Redis·MinIO·Infinity·OCR 상태 포트는 대상 PC의 `127.0.0.1`에만 공개됩니다. Windows 방화벽에서는 실제로 필요한 사용자용 포트만 사내망 프로필에 허용하십시오.

RAGFlow 컨테이너 내부의 `9382`는 Windows에서 직접 접속할 포트가 아닙니다. 이 번들은 공식 MCP를 호스트 `42303`에 매핑합니다. `42300`은 UI, `42301`은 REST API이므로 UI 포트의 `/api/v1/chat`을 API 연결 시험에 사용하지 마십시오.

| 포트 | 용도 |
| --- | --- |
| `42300` | LIG AI Knowledge Hub 웹 UI |
| `42301` | RAGFlow REST API |
| `42302` | RAGFlow Admin API |
| `42303` | RAGFlow 공식 MCP `/mcp` |
| `42306` | LIG 관리 MCP `/mcp` |
| `42308` | MySQL |
| `42309` / `42310` | MinIO API / Console |
| `42311` | Valkey |
| `42316` | 한국어 PaddleOCR API 및 `/health` |
| `42317` | 선택형 Qwen3 임베딩 API 및 `/health` |
| `42312`~`42314` | Infinity |

다른 장비에서는 `http://<RAG-PC-IP>:42300`과 `http://<RAG-PC-IP>:42303/mcp`를 사용합니다. 바인딩 주소를 특정 사내 IP로 좁히려면 `LIG-Deployment\.env.lig`의 해당 `0.0.0.0:<포트>`를 `<RAG-PC-IP>:<포트>`로 변경하십시오.

## 5. 공식 MCP와 관리 MCP

공식 MCP와 LIG 관리 MCP는 사용자 전달형 인증으로 실행됩니다. 각 사용자는 Web UI의 개인 설정 API 메뉴에서 자신의 RAGFlow API 키를 발급하고 MCP 클라이언트에 `Authorization: Bearer <개인 API 키>`로 등록해야 합니다. MCP가 이 키를 RAGFlow에 그대로 전달하므로 Web UI와 같은 테넌트·데이터셋 권한이 적용됩니다.

- 공식 MCP: `http://<RAG-PC-IP>:42303/mcp` — 개인 RAGFlow API 키 Bearer 필수
- LIG 관리 MCP: `http://<RAG-PC-IP>:42306/mcp` — 같은 개인 RAGFlow API 키 Bearer 필수

Bearer가 없거나 다른 사용자의 키를 사용하면 연결 또는 도구 호출이 거부됩니다. 개인 API 키를 공동 계정처럼 공유하지 마십시오. `.env.secret`은 서버에서만 보관하며 메일, Git, 공용 파일 서버에 올리지 마십시오. LIG 관리 MCP에 전달할 로컬 파일은 `LIG-Deployment\mcp-files`에 넣고 MCP 도구에는 `/data/<파일명>` 경로를 사용합니다.

### 폐쇄망 팀 멤버 추가

메일 초대는 사용하지 않습니다. 추가할 사용자가 먼저 가입 화면에서 사내 계정을 만든 다음 팀 소유자가 `개인 설정 → 팀 → 멤버 추가`에서 가입 이메일을 입력합니다. 등록된 활성 계정은 이메일 발송이나 수락 단계 없이 즉시 일반 팀원이 됩니다. 이후 데이터셋 권한을 `team`으로 저장하면 해당 팀원은 자신의 개인 API 키로 Web UI와 두 MCP에서 공유 데이터셋에 접근합니다. 등록되지 않은 이메일, 다른 팀 소유자 계정, 이미 추가된 계정은 거부됩니다.

## 6. 내부 vLLM 생성 모델 등록

RAGFlow 웹 UI의 `설정 → 모델 공급자`에서 OpenAI 호환 공급자를 추가합니다.

- Docker 호스트에서 vLLM 실행: `http://host.docker.internal:<포트>/v1`
- 별도 사내 서버에서 실행: `http://<사내-vLLM-IP>:<포트>/v1`
- 모델명: vLLM의 `--served-model-name`과 정확히 같은 값
- API 키: vLLM에 인증이 없더라도 UI가 값을 요구하면 사내 정책에 맞는 비밀값 또는 서버가 허용하는 값을 입력

RAGFlow 컨테이너에서 `127.0.0.1`은 대상 Windows 호스트나 별도 vLLM 서버를 의미하지 않습니다. 반드시 위 주소 형식을 사용합니다. 등록 후 기본 LLM으로 선택하고 간단한 채팅 호출로 연결을 확인합니다.

## 7. 내부 embedding 모델 등록

생성 LLM과 embedding 모델은 서로 다른 역할이며, 생성 모델만 등록해서는 문서 인덱싱이 완료되지 않습니다. 사내 embedding endpoint가 있으면 다음과 같이 등록합니다.

- Base URL: `http://host.docker.internal:<embedding-port>/v1` 또는 `http://<내부-IP>:<embedding-port>/v1`
- 모델명: embedding 서버의 served model name
- 모델 유형: `Embedding`
- 기본 Embedding 모델로 지정

새 embedding 모델을 선택한 뒤 기존 데이터셋에 다른 모델의 벡터를 섞지 마십시오. 모델이나 벡터 차원이 변경되면 새 데이터셋으로 시험하거나 기존 데이터셋을 재인덱싱해야 합니다.

사내 embedding endpoint가 없고 번들을 `-IncludeEmbedding` 옵션으로 만들었다면 동봉된 선택형 CPU 서비스를 설치합니다.

```powershell
.\install-embedding-cpu.ps1
```

이 명령은 기본 런타임과 분리된 `lig-qwen3-embedding-images-0.6b.tar.gz`의 SHA-256과 이미지 ID를 확인한 후 다음 구성만 추가합니다.

- 모델: `Qwen/Qwen3-Embedding-0.6B`
- 고정 리비전: `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`
- 라이선스: Apache-2.0
- 런타임: Hugging Face TEI `cpu-1.9`
- 벡터 차원: 1024
- RAGFlow 최대 입력: 2,048 토큰, 초과 시 자동 절단
- 장치: CPU 전용. DeepDoc 또는 PaddleOCR-VL VLM과 VRAM을 경쟁하지 않음

RAGFlow 웹 UI의 `설정 → 모델 공급자`에서 다음 값을 등록합니다.

- 공급자: `HuggingFace`
- 인스턴스명: `LIG-Qwen3-CPU`
- 모델명: `Qwen/Qwen3-Embedding-0.6B`
- 유형: `Embedding`
- Base URL: `http://qwen3-embedding:8080`
- API 키: 비워 둠
- 최대 토큰: `2048`

`http://127.0.0.1:42317`은 Windows 호스트의 점검 주소입니다. RAGFlow는 Docker 네트워크 내부 주소인 `http://qwen3-embedding:8080`을 사용해야 합니다. 어댑터는 검색 질의에만 Qwen 권장 instruction을 붙이고 문서 청크에는 붙이지 않습니다.

`.env.lig`의 `MAX_CONCURRENT_EMBEDDERS=4`는 한 작업이 동시에 보내는 임베딩 배치 수이며 처리량을 결정하는 값입니다. 12코어 호스트에서 텍스트 4개짜리 요청 16건을 동시성별로 측정한 결과입니다.

| 동시성 | 1 | 2 | 4 | 6 | 8 |
|---|---|---|---|---|---|
| 소요 | 80.94초 | 93.20초 | **11.36초** | 11.35초 | 12.59초 |

2에서 4로 넘어가는 지점이 완만한 곡선이 아니라 **절벽**입니다. `qwen3-embedding-tei`의 `--max-batch-requests 4`와 같은 값이기 때문입니다. TEI는 요청 4건이 찰 때까지 기다렸다가 처리하므로, 그 아래에서는 매 요청이 대기 비용만 냅니다. 동시성 2가 1보다 느린 것이 그 증거입니다. 따라서 이 두 값은 독립 조정 대상이 아니라 한 쌍이며, **6 이상으로 올려도 이득이 없고 8에서는 오히려 느려집니다.** 문제가 생기면 `1`로 되돌리면 재빌드 없이 기존 동작으로 복귀합니다.

`EMBEDDING_BATCH_SIZE=4`는 요청 한 건에 담는 텍스트 수이고 공급자 요청 제한시간은 300초입니다. 이 값과 `qwen3-embedding-tei`의 `--max-batch-tokens 2048`은 올려도 처리량이 늘지 않습니다. 같은 호스트에서 예산 2048·4096·8192의 배속이 모두 7.3배로 동일했고 절대 시간은 2048이 가장 빨랐습니다. 반면 기동 시 메모리는 2048에서 3.3GB, 8192에서 15.3GB, 32768에서 20GB 이상으로 치솟아 Docker 엔진이 컨테이너 조회에 실패할 정도의 압박을 유발했습니다. 워밍업 이후 상주 메모리는 어느 값이든 약 2.35GB로 같습니다. 즉 이 값을 올리는 것은 기동 스파이크만 키우므로 그대로 두십시오. `EMBEDDING_MAX_CONCURRENT_REQUESTS=6`은 어댑터가 TEI로 동시에 넘기는 요청 수입니다. 어댑터는 문서 처리와 사용자 검색 질의를 함께 받으므로, `MAX_CONCURRENT_EMBEDDERS`와 같은 값이면 문서 처리가 전 슬롯을 점유해 검색이 뒤에서 대기합니다. 4보다 2 큰 값이 그 여유분입니다. TEI 자체의 `--max-concurrent-requests 8`이 상한이며, **이 값은 올리지 마십시오.** 16으로 올려 측정했을 때 동시성 4의 소요가 11.36초에서 96.95초로 늘어 전 구간이 약 절반 속도가 됐습니다. `HUGGINGFACE_EMBEDDING_MAX_RETRIES=0`은 문서 처리 중 일시적인 backend 재기동에도 제한 횟수 없이 재연결합니다. 대화 검색은 `HUGGINGFACE_EMBEDDING_QUERY_MAX_RETRIES=3`으로 무한 대기하지 않습니다. CPU 코어, 메모리 또는 전체 처리량에 상한을 거는 설정이 아닙니다.

DeepDoc/PaddleOCR-VL GPU와 이 embedding 서비스는 별개입니다. Qwen3와 일반 PP-OCRv5는 CPU에서 실행되므로 12 GiB GPU VRAM을 사용하지 않지만, Docker 시스템 RAM을 사용합니다. Qwen3의 유휴 시스템 RAM은 약 1.5 GiB이며 Compose는 임의의 CPU·RAM 상한을 두지 않습니다.

기본 이미지 반입 후에는 `verify-cpu-images.ps1`을 실행해 암호 PDF 본문 보존, 일반 문서 암호 상태 정리, OCR 연동 및 청킹 런타임 패치 포함 여부를 RAGFlow 이미지 내부에서 확인할 수 있습니다. 한국어 PaddleOCR 모델은 기본 이미지에 없으며 `install-paddleocr.ps1`이 별도 이미지의 모델 메타데이터와 health를 검증합니다.

새 embedding 모델을 기본값으로 지정해도 기존 데이터셋의 `embd_id`는 자동 변경되지 않습니다. 기존 데이터셋은 그대로 유지하고 새 데이터셋으로 검색 품질을 검증하십시오. 기존 데이터셋을 전환해야 한다면 문서를 전부 재인덱싱해야 하며, 서로 다른 모델의 벡터를 한 데이터셋에 섞지 마십시오.

### 한국어 OCR 선택

한국어 PDF에서 중국어나 특수문자가 생성되면 임베딩 문제가 아니라 OCR 문자 집합 문제입니다.

번들을 `-IncludePaddleOcr`로 만들었다면 기본 설치 후 한 번만 추가 설치합니다.

```powershell
.\install-paddleocr.ps1
.\test-paddleocr.ps1
```

1. 데이터셋 기본 설정의 언어를 `Korean`으로 지정합니다.
2. 텍스트 선택과 복사가 정상인 PDF는 PDF 파서 `Plain Text`를 사용합니다.
3. 스캔 PDF나 글꼴 매핑이 깨진 PDF는 `start-paddleocr.ps1`을 먼저 실행하고 청킹 `Naive`, PDF 파서 `paddleocr-from-env`를 선택합니다. 이 파서는 PDF를 기본 40쪽 단위로 나누되 각 작업 범위의 페이지만 OCR 서비스에 보내므로 전체 원본을 작업마다 반복 처리하지 않습니다. 내부 API URL, 토큰과 `PP-OCRv5`는 자동 적용되므로 별도로 입력하지 않습니다.
4. 파서를 바꾼 뒤 기존의 잘못된 청크를 삭제하고 문서를 다시 처리합니다.

DeepDOC는 영어·중국어 문서와 표·레이아웃·좌표 처리용으로 유지합니다. PaddleOCR 한국어 모델은 한국어·영어·숫자 인식에 집중하므로 모든 문서에 대한 무조건적인 대체재는 아닙니다.

업로드 창은 PDF, DOC/DOCX, XLS/XLSX, PPT/PPTX, HWP/HWPX별 파일 열기 비밀번호를 받습니다. 암호화된 최신 Office와 HWPX는 업로드 때 검증하고 파싱 직전에 메모리에서 복호화합니다. 일반 HWP 5와 HWPX도 텍스트로 처리하지만 암호화된 바이너리 HWP는 HWPX 또는 DOCX로 다시 저장해야 합니다. 배포용 HWP, 편집·시트 보호, Microsoft IRM/MIP/AIP 및 FASOO DRM은 권한 우회 대상이 아닙니다. `.env.secret`의 활성/이전 키를 잃으면 저장된 문서 암호를 다시 사용할 수 없으므로 DB와 같은 복구 시점으로 암호화 백업하십시오. 전체 확장자 표와 키 감사·회전·복구 절차는 상위 `DOCUMENT-COMPATIBILITY.ko.md`를 따릅니다.

암호 PDF의 작업 기록이 `OCR started`까지 진행됐다면 파일 열기 암호는 통과한 상태입니다. 소유자 암호가 필요한 권한 제한 PDF는 OCR 전에 명시적인 권한 오류가 표시됩니다.

온라인 NVIDIA `nvidia/llama-nemotron-embed-vl-1b-v2`와 로컬 Qwen3는 벡터 차원과 의미 공간이 다릅니다. 운영 모델을 결정한 뒤 고정하고, 변경 시 전체 재인덱싱 계획을 세우십시오.

## 8. 문서 처리 설정

기본 성능 설정은 `LIG-Deployment\.env.lig`에 있습니다. 기본 `API_PROXY_SCHEME=python`은 문서 암호 처리와 OCR/청킹 보강이 모두 적용되는 실행 경로입니다. upstream Go/Hybrid 모드로 바꿀 수는 있지만 해당 LIG 확장 전체는 보장되지 않습니다.

```dotenv
TASK_EXECUTOR_WORKERS=3
MAX_CONCURRENT_TASKS=1
MAX_CONCURRENT_CHUNK_BUILDERS=1
PDF_TASK_PAGE_SIZE=40
ADAPTIVE_PDF_TASK_PAGE_SIZE=false
```

API와 task executor는 별도 컨테이너입니다. 기본 구성은 task executor 3개가 각각 task/parser 하나를 받아 PDF의 40쪽 범위 작업을 총 3개까지 병렬 처리합니다. 일반 PaddleOCR은 별도 시작한 경우에만 같은 작업 구조를 사용합니다. `MAX_CONCURRENT_TASKS`와 `MAX_CONCURRENT_CHUNK_BUILDERS`는 worker당 값이므로 worker와 함께 모두 3으로 설정하면 최대 9개 파서가 열립니다. 데이터셋의 `task_page_size`가 `PDF_TASK_PAGE_SIZE`보다 우선합니다. 이 공통값은 DeepDOC, Plain Text, Docling 등 페이지 분할이 가능한 PDF 파서에 적용되고, PaddleOCR에는 `PADDLEOCR_TASK_PAGE_SIZE=40` 전송 상한이 추가 적용됩니다. `ADAPTIVE_PDF_TASK_PAGE_SIZE=false`가 기본이므로 메모리에 따라 40쪽이 더 작게 바뀌지 않습니다. 메모리 적응 축소가 필요한 장비에서만 이를 `true`로 변경합니다. `One`, 지식 그래프 및 목차 추출처럼 전체 문서 문맥이 필요한 모드는 분할하지 않습니다. 문서 크기·페이지 수 제한은 기본적으로 비활성화되어 있으므로 큰 문서는 느리더라도 계속 진행됩니다. 취소 신호를 받은 파서는 협력 중단하며, 네이티브 라이브러리나 외부 파서가 5초 이상 취소를 무시하면 API가 아니라 격리 task executor 프로세스만 자동 재기동합니다. 컨테이너 교체나 비정상 종료로 과거 consumer에 묶인 Redis pending은 기본 300초 유휴 후 현재 worker가 자동 인계하고, task lease를 확인한 뒤 종료 작업은 승인 처리하고 유효 작업은 이어서 수행합니다. 로컬 Qwen3 요청 제한시간은 300초이고 embedding batch는 4입니다. 값을 변경한 후 `stop.ps1`, `start.ps1` 순서로 적용합니다.

GPU 설치·시작·진단 스크립트도 `.env.lig`의 `TASK_EXECUTOR_WORKERS`, `MAX_CONCURRENT_TASKS`, `MAX_CONCURRENT_CHUNK_BUILDERS`를 그대로 사용하며 별도 강제값을 적용하지 않습니다. DeepDOC는 worker마다 모델을 적재할 수 있으므로 GPU 메모리가 부족한 환경에서는 운영자가 `TASK_EXECUTOR_WORKERS=1`로 직접 낮춘 뒤 재시작하십시오.

텍스트 선택이 가능한 대형 PDF에서 속도를 우선하면 데이터셋의 레이아웃 인식을 `Plain Text`로 시험합니다. 스캔 문서, 표, 다단 편집 품질이 중요하면 `DeepDOC`을 사용하되 CPU 처리에는 시간이 오래 걸릴 수 있습니다. 실행 중 같은 문서의 재처리를 반복하면 이전 작업이 정리되는 동안 UI 진행률 갱신이 지연될 수 있습니다.

### 선택 설치: PaddleOCR-VL-1.6

인터넷 연결 컴퓨터에서 번들을 만들 때 다음 옵션을 함께 지정하면 공식 자산 기반 CPU pipeline 이미지, 공식 PaddleOCR-VL-1.6 vLLM 오프라인 이미지와 호환 게이트웨이가 별도 압축파일로 포함됩니다. 기반 pipeline과 VLM 원본 이미지가 약 10 GB와 15 GB이므로 충분한 디스크 공간을 확보하십시오.

```powershell
pwsh LIG-Deployment/lig-ragflow.ps1 paddleocr-vl-pull
pwsh LIG-Deployment/lig-ragflow.ps1 paddleocr-vl-build
pwsh LIG-Deployment/airgap-export.ps1 `
  -Destination "D:\LIG-RAGFlow-Airgap" `
  -IncludeGpu `
  -IncludeEmbedding `
  -IncludePaddleOcr `
  -IncludePaddleOcrVl
```

폐쇄망에서는 기본 GPU 설치를 완료한 다음 선택 설치 파일을 실행합니다.

```powershell
.\install-paddleocr-vl.ps1
.\test-paddleocr-vl.ps1
```

데이터셋 설정에서 `PaddleOCR` PDF 파서를 고르면 `start-paddleocr.ps1`로 일반 서비스를 실행한 경우 `paddleocr-from-env`가 표시되고, 선택 설치한 VL gateway의 health가 정상일 때만 `paddleocr-vl-from-env`도 표시됩니다. RAGFlow 내부 공급자 엔진 이름만 같고 URL·토큰·알고리즘·모델 인스턴스는 분리되어 있으므로 일반 OCR 설정을 덮어쓰지 않습니다. VL 모델이 바로 보이지 않으면 `paddleocr-vl-status`로 VLM·CPU pipeline·gateway 상태를 확인하십시오.

번들 Job API와 사내 원격 PaddleX 이미지 API는 모델 또는 데이터셋 설정의 PDF 렌더링 DPI를 작업별로 사용하며 기본값은 144입니다. MIL-STD-2525C 표본의 144/180/216/240/300 DPI 비교에서 144 DPI가 가장 높은 평균 단어 F1과 가장 낮은 픽셀 비용을 보였습니다. 작은 글자 누락이 확인된 스캔 문서만 216 DPI를 시험하십시오.

12 GiB GPU 기본값은 선택 실행한 일반 PP-OCRv5와 VL 레이아웃 검출을 CPU에서 처리하고 0.9B VLM만 PaddleOCR 계열 GPU 작업으로 실행합니다. vLLM은 eager 모드, GPU 비율 0.60, API server 1개, batch tokens 16,384로 시작합니다. 이 값은 모델 컨텍스트와 맞춘 안정적인 시작점입니다. `No available memory for the cache blocks`가 계속되면 `paddleocr-vl-status`에서 여유 VRAM과 최근 오류를 확인하고 다른 DeepDOC 작업을 중지한 뒤 GPU 비율을 0.05씩 올려 시험하십시오. 너무 높이면 DeepDOC가 사용할 VRAM이 사라지므로 측정 없이 크게 올리지 마십시오.

장치 배치는 다음과 같습니다.

| 서비스 | 장치 | 비고 |
| --- | --- | --- |
| 일반 `paddleocr-from-env` | CPU | 한국어 PP-OCRv5, `start-paddleocr.ps1`로 선택 실행 |
| VL 레이아웃 pipeline | CPU | GPU 예약 없음 |
| `paddleocr-vl-from-env`의 0.9B VLM | GPU | 선택 설치 |
| DeepDOC | GPU 설치 시 GPU | VLM과 VRAM 공유 |

상태와 계층별 연결을 확인합니다.

```powershell
.\start-paddleocr-vl.ps1
pwsh LIG-Deployment\lig-ragflow.ps1 paddleocr-vl-status
.\test-paddleocr-vl.ps1
```

`paddleocr-vl-status`는 VLM의 전체·사용·여유 VRAM과 최근 KV cache/OOM 로그를 표시합니다. `test-paddleocr-vl.ps1`은 VLM, CPU pipeline, gateway 순서로 검사하므로 어느 계층이 실패했는지 바로 구분할 수 있습니다.

## 9. 정상 상태 확인

```powershell
.\diagnostics.ps1 > diagnostics.json
```

다음을 확인합니다.

- `DockerError`와 `ApiError`가 `null`
- `Connectivity.ApiPing`, `Connectivity.OfficialMcp.Reachable`, `Connectivity.ManagementMcp.Reachable`가 `true`
- `Health`의 document engine, storage, database, redis가 모두 `green`
- `CurrentTaskExecutorHeartbeatCount`가 `.env.lig`의 worker 수와 일치
- 웹 UI가 HTTP 200으로 열림
- 관리 MCP 컨테이너가 `healthy`

최근 종료된 컨테이너 heartbeat가 30분간 남을 수 있으므로 `TaskExecutorHeartbeats`에서는 `CurrentContainer=true`인 항목만 현재 worker로 판단합니다.

## 10. 데이터와 백업

컨테이너를 다시 만들어도 문서와 인덱스는 Docker named volume에 유지됩니다. 다음 명령은 서비스를 잠시 정지하여 MySQL·MinIO·Infinity·Redis를 같은 시점으로 보관하고, 파일별 SHA-256이 기록된 `manifest.json`을 만듭니다. 기본 대상은 바탕화면 `LIG-RAGFlow-Backups`이며 이전에 실행 중이던 선택 서비스도 다시 시작합니다.

```powershell
.\backup.ps1
.\backup.ps1 -Destination "D:\RAGFlow-Backup\20260828"
```

복원은 기존 볼륨 내용을 교체하므로 명시적 확인이 필요합니다. 설정 파일까지 되돌릴 때만 `-RestoreConfiguration`을 추가합니다.

```powershell
.\restore.ps1 -Source "D:\RAGFlow-Backup\20260828" -ConfirmRestore
```

백업 폴더에는 다음 설정 파일도 포함됩니다.

- `LIG-Deployment\.env.lig`
- `LIG-Deployment\.env.secret` — 별도 암호화 보관
- 사내 인증서와 리버스 프록시 설정

`docker compose down -v`, Docker Desktop의 전체 데이터 삭제, named volume 삭제는 데이터를 제거하므로 실행하지 마십시오.

## 11. 업데이트와 롤백

새 번들은 기존 폴더 위에 덮어쓰지 말고 별도 폴더에 설치 설명서와 manifest를 함께 보관합니다. 데이터 이전 및 호환성을 확인한 후 전환합니다.

CPU 커스텀 UI 문제 시 `LIG-Deployment\.env.lig`의 `RAGFLOW_IMAGE`를 다음 공식 이미지로 바꾸고 재시작하면 UI를 롤백할 수 있습니다. GPU 프로필에는 CUDA 라이브러리를 포함한 `RAGFLOW_GPU_IMAGE`를 유지해야 합니다.

```dotenv
RAGFLOW_IMAGE=infiniflow/ragflow:v0.26.4
```

백엔드 버전을 올리는 작업은 단순 이미지 교체로 처리하지 말고 DB 마이그레이션과 릴리스 노트를 별도로 검토해야 합니다.

## 12. 사내 운영 전 필수 변경

기본 번들은 UI·API·MCP를 사내망에서 접속할 수 있도록 `0.0.0.0`에, DB·Redis·MinIO·Infinity와 OCR 상태 포트는 `127.0.0.1`에 바인딩하고 회원가입을 허용합니다. 여러 사내 사용자가 접속하는 운영 서버에서는 다음 항목을 별도로 확정해야 합니다.

- 리버스 프록시와 사내 TLS 인증서 적용
- 웹/API 공개 주소를 서버 IP로 변경하고 필요한 포트만 방화벽에서 허용
- 최초 관리자 생성 후 `REGISTER_ENABLED=0`으로 자체 회원가입 차단
- `.env.secret`의 API 키 교체와 별도 암호화 백업
- 내부 생성 LLM 및 embedding endpoint의 고정 IP/DNS, 인증서와 API 키 설정
- Docker 데이터 디스크와 named volume 정기 백업
- NVIDIA 드라이버·CUDA 호환 버전 고정 및 변경 관리
- 실제 사내 문서로 DeepDoc GPU 처리시간, 검색 정답률과 인용 페이지 검증
