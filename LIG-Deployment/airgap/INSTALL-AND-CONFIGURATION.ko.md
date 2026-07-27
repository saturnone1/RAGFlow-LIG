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
.\install-gpu.ps1
```

설치 프로그램은 다음 작업을 자동 수행합니다.

1. manifest와 모든 파일의 SHA-256 검증
2. gzip Docker 이미지 아카이브 로드
3. `.env.secret` 예제 생성
4. 로그와 MCP 파일 교환 폴더 생성
5. RAGFlow, 한국어 PaddleOCR, Infinity, MySQL, MinIO, Valkey, 공식 MCP, LIG 관리 MCP 시작

`install-gpu.ps1`은 이미지 로드 후 임시 컨테이너에서 GPU 이름과 VRAM, DeepDOC 및 PaddleOCR의 CUDAExecutionProvider를 검증합니다. 검증 실패 시 CPU 모드로 조용히 대체하지 않고 설치를 중단합니다.

CPU와 GPU 설치 모두 한국어 PP-OCRv5 모델이 포함된 PaddleOCR 서비스를 시작합니다. CPU 설치는 CPUExecutionProvider, GPU 설치는 CUDAExecutionProvider를 사용하며 폐쇄망에서 모델을 추가 다운로드하지 않습니다.

완료 후 `http://127.0.0.1:42300`에 접속합니다. 최초 관리자 계정을 만든 뒤 로그인합니다.

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
.\logs.ps1
```

- `start.ps1`: 기존 데이터 볼륨을 유지하며 서비스 시작
- `start-gpu.ps1`: NVIDIA DeepDoc GPU 프로필과 executor 1개로 시작. 12 GiB는 GPU VRAM 기준이며 CPU·시스템 RAM 상한을 설정하지 않음
- `install-embedding-cpu.ps1`: 별도 Qwen3 이미지 아카이브를 검증·로드하고 CPU 임베딩 서비스 시작
- `start-embedding-cpu.ps1` / `stop-embedding.ps1`: 선택형 임베딩 서비스만 시작 또는 중지
- `test-embedding.ps1`: health와 한국어·영어 1024차원 배치 추론 검증
- `stop.ps1`: 컨테이너와 네트워크만 중지·제거하며 문서 데이터는 삭제하지 않음
- `status.ps1`: 컨테이너와 Docker 디스크 사용량 확인
- `diagnostics.ps1`: health, 현재 task executor, 자원 사용량, 최근 처리시간과 오류를 JSON으로 출력
- `diagnostics-gpu.ps1`: GPU 프로필을 기준으로 같은 진단 실행
- `logs.ps1`: 최근 컨테이너 로그 출력
- 한국어 PaddleOCR 상태: `http://127.0.0.1:42316/health`

진단 결과를 파일로 보관하려면 다음과 같이 실행합니다.

```powershell
.\diagnostics.ps1 > diagnostics.json
```

## 4. 포트

모든 기본 포트는 대상 PC의 `127.0.0.1`에만 공개됩니다.

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

다른 장비에서 웹 UI나 API에 접근해야 한다면 방화벽·리버스 프록시·TLS 정책을 먼저 정한 후 `LIG-Deployment\.env.lig`의 해당 `127.0.0.1:<포트>` 바인딩을 사내 IP 또는 `0.0.0.0:<포트>`로 변경합니다. 인증과 방화벽 없이 외부 인터페이스에 공개하지 마십시오.

## 5. API 키와 관리 MCP

웹 UI에서 사용자 설정의 API 키 메뉴를 열어 로컬 RAGFlow API 키를 생성합니다. 다음 파일의 자리표시자를 생성한 키로 교체합니다.

```text
LIG-Deployment\.env.secret
```

```dotenv
RAGFLOW_MCP_API_KEY=ragflow-발급받은-로컬-키
```

키를 변경한 후 서비스를 재시작합니다. GPU 설치 장비는 마지막 명령을 `start-gpu.ps1`로 바꿉니다.

```powershell
.\stop.ps1
.\start.ps1
```

`.env.secret`을 메일, Git, 공용 파일 서버에 올리지 마십시오. LIG 관리 MCP에 전달할 로컬 파일은 `LIG-Deployment\mcp-files`에 넣고 MCP 도구에는 `/data/<파일명>` 경로를 사용합니다.

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

사내 embedding endpoint가 없다면 번들에 동봉된 선택형 CPU 서비스를 설치합니다.

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
- 장치: CPU 전용. DeepDoc 또는 PaddleOCR GPU와 VRAM을 경쟁하지 않음

RAGFlow 웹 UI의 `설정 → 모델 공급자`에서 다음 값을 등록합니다.

- 공급자: `HuggingFace`
- 인스턴스명: `LIG-Qwen3-CPU`
- 모델명: `Qwen/Qwen3-Embedding-0.6B`
- 유형: `Embedding`
- Base URL: `http://qwen3-embedding:8080`
- API 키: 비워 둠
- 최대 토큰: `2048`

`http://127.0.0.1:42317`은 Windows 호스트의 점검 주소입니다. RAGFlow는 Docker 네트워크 내부 주소인 `http://qwen3-embedding:8080`을 사용해야 합니다. 어댑터는 검색 질의에만 Qwen 권장 instruction을 붙이고 문서 청크에는 붙이지 않습니다.

`.env.lig`의 `EMBEDDING_BATCH_SIZE=2`는 CPU Qwen3 요청이 LIG 이미지의 60초 공급자 제한시간 안에 끝나도록 한 요청에 묶는 청크 수를 조정합니다. CPU 코어, 메모리 또는 전체 처리량에 상한을 거는 설정이 아닙니다.

DeepDoc/PaddleOCR GPU와 이 embedding 서비스는 별개입니다. Qwen3는 CPU에서 실행되므로 12 GiB GPU VRAM을 사용하지 않지만, Docker 시스템 RAM을 유휴 상태에서 약 1.5 GiB 추가 사용합니다. Compose는 임의의 CPU·RAM 상한을 두지 않습니다.

새 embedding 모델을 기본값으로 지정해도 기존 데이터셋의 `embd_id`는 자동 변경되지 않습니다. 기존 데이터셋은 그대로 유지하고 새 데이터셋으로 검색 품질을 검증하십시오. 기존 데이터셋을 전환해야 한다면 문서를 전부 재인덱싱해야 하며, 서로 다른 모델의 벡터를 한 데이터셋에 섞지 마십시오.

### 한국어 OCR 선택

한국어 PDF에서 중국어나 특수문자가 생성되면 임베딩 문제가 아니라 OCR 문자 집합 문제입니다.

1. 데이터셋 기본 설정의 언어를 `Korean`으로 지정합니다.
2. 텍스트 선택과 복사가 정상인 PDF는 PDF 파서 `Plain Text`를 사용합니다.
3. 스캔 PDF나 글꼴 매핑이 깨진 PDF는 청킹 `Naive`, PDF 파서 `paddleocr-from-env`를 선택합니다. 이 파서를 쓰는 데이터셋은 PDF 전체를 단일 RAGFlow 작업으로 처리해 작업 분할에 따른 중복 OCR을 방지합니다. 내부 API URL, 토큰과 `PP-OCRv5`는 자동 적용되므로 별도로 입력하지 않습니다.
4. 파서를 바꾼 뒤 기존의 잘못된 청크를 삭제하고 문서를 다시 처리합니다.

DeepDOC는 영어·중국어 문서와 표·레이아웃·좌표 처리용으로 유지합니다. PaddleOCR 한국어 모델은 한국어·영어·숫자 인식에 집중하므로 모든 문서에 대한 무조건적인 대체재는 아닙니다.

온라인 NVIDIA `nvidia/llama-nemotron-embed-vl-1b-v2`와 로컬 Qwen3는 벡터 차원과 의미 공간이 다릅니다. 운영 모델을 결정한 뒤 고정하고, 변경 시 전체 재인덱싱 계획을 세우십시오.

## 8. 문서 처리 설정

기본 성능 설정은 `LIG-Deployment\.env.lig`에 있습니다.

```dotenv
TASK_EXECUTOR_WORKERS=2
```

Compose는 CPU와 시스템 RAM 사용량을 제한하지 않습니다. CPU 설치의 task executor 초기값은 2이고, 문서 bulk와 thread pool은 RAGFlow upstream 기본값을 사용합니다. 로컬 Qwen3는 60초 요청 제한을 기준으로 embedding batch를 2로 설정합니다. 값을 변경한 후 `stop.ps1`, `start.ps1` 순서로 적용합니다.

GPU 설치 스크립트는 12 GiB VRAM에서 DeepDoc 모델이 작업 실행기마다 중복 적재되는 위험을 줄이기 위해 `TASK_EXECUTOR_WORKERS=1`을 적용합니다. 실제 GPU 모델과 VRAM 사용량을 측정한 뒤에만 2개로 올리십시오.

텍스트 선택이 가능한 대형 PDF에서 속도를 우선하면 데이터셋의 레이아웃 인식을 `Plain Text`로 시험합니다. 스캔 문서, 표, 다단 편집 품질이 중요하면 `DeepDOC`을 사용하되 CPU 처리에는 시간이 오래 걸릴 수 있습니다. 실행 중 같은 문서의 재처리를 반복하면 이전 작업이 정리되는 동안 UI 진행률 갱신이 지연될 수 있습니다.

## 9. 정상 상태 확인

```powershell
.\diagnostics.ps1 > diagnostics.json
```

다음을 확인합니다.

- `DockerError`와 `ApiError`가 `null`
- `Health`의 document engine, storage, database, redis가 모두 `green`
- `CurrentTaskExecutorHeartbeatCount`가 `.env.lig`의 worker 수와 일치
- 웹 UI가 HTTP 200으로 열림
- 관리 MCP 컨테이너가 `healthy`

최근 종료된 컨테이너 heartbeat가 30분간 남을 수 있으므로 `TaskExecutorHeartbeats`에서는 `CurrentContainer=true`인 항목만 현재 worker로 판단합니다.

## 10. 데이터와 백업

컨테이너를 다시 만들어도 문서와 인덱스는 Docker named volume에 유지됩니다. 중요한 운영 환경에서는 Docker Desktop 데이터 디스크와 다음 설정 파일을 정기적으로 백업합니다.

- `LIG-Deployment\.env.lig`
- `LIG-Deployment\.env.secret` — 별도 암호화 보관
- 사내 인증서와 리버스 프록시 설정

`docker compose down -v`, Docker Desktop의 전체 데이터 삭제, named volume 삭제는 데이터를 제거하므로 실행하지 마십시오.

## 11. 업데이트와 롤백

새 번들은 기존 폴더 위에 덮어쓰지 말고 별도 폴더에 설치 설명서와 manifest를 함께 보관합니다. 데이터 이전 및 호환성을 확인한 후 전환합니다.

커스텀 UI 문제 시 `LIG-Deployment\.env.lig`의 `RAGFLOW_IMAGE`를 다음 공식 이미지로 바꾸고 재시작하면 UI를 롤백할 수 있습니다.

```dotenv
RAGFLOW_IMAGE=infiniflow/ragflow:v0.26.4
```

백엔드 버전을 올리는 작업은 단순 이미지 교체로 처리하지 말고 DB 마이그레이션과 릴리스 노트를 별도로 검토해야 합니다.

## 12. 사내 운영 전 필수 변경

기본 번들은 단일 PC에서 안전하게 시험하도록 모든 포트를 `127.0.0.1`에 바인딩하고 회원가입을 허용합니다. 여러 사내 사용자가 접속하는 운영 서버에서는 다음 항목을 별도로 확정해야 합니다.

- 리버스 프록시와 사내 TLS 인증서 적용
- 웹/API 공개 주소를 서버 IP로 변경하고 필요한 포트만 방화벽에서 허용
- 최초 관리자 생성 후 `REGISTER_ENABLED=0`으로 자체 회원가입 차단
- `.env.secret`의 API 키 교체와 별도 암호화 백업
- 내부 생성 LLM 및 embedding endpoint의 고정 IP/DNS, 인증서와 API 키 설정
- Docker 데이터 디스크와 named volume 정기 백업
- NVIDIA 드라이버·CUDA 호환 버전 고정 및 변경 관리
- 실제 사내 문서로 DeepDoc GPU 처리시간, 검색 정답률과 인용 페이지 검증
