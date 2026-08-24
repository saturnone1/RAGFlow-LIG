# LIG AI Knowledge Hub 에어갭 설치

이 폴더만 폐쇄망 Windows PC로 복사하면 됩니다. 인터넷 연결이나 원본 Git 저장소는 필요하지 않습니다.

현재 manifest 형식은 `bundleFormat=12`입니다. CPU·GPU 설치가 일반 PaddleOCR CPU 이미지를 공용으로 사용하고 선택형 PaddleOCR-VL VLM만 GPU를 사용하도록 이미지 구성이 정리되었으므로 이전 형식의 이미지 압축파일은 재사용할 수 없습니다. 폐쇄망 반입 전 새 번들을 생성하십시오.

상세 설치, API 키, 포트, 내부 vLLM 생성/embedding 모델 등록, 운영 및 백업 절차는 `INSTALL-AND-CONFIGURATION.ko.md`를 먼저 읽으십시오.

## 준비 사항

- Windows 10/11과 Docker Desktop(Compose v2 포함)
- C 드라이브 여유 공간 최소 20 GiB
- `42300`~`42317`의 `.env.lig` 지정 로컬 포트가 비어 있어야 함. 선택형 PaddleOCR-VL은 `42318`도 사용
- GPU 설치: NVIDIA GPU, 최신 드라이버, Docker의 NVIDIA Container Toolkit/GPU 접근, Docker 메모리 20 GiB 이상 권장

## 설치와 운영

Docker Desktop을 시작한 뒤 이 폴더에서 PowerShell을 열고 실행합니다.

```powershell
# CPU DeepDoc
.\install.ps1

# NVIDIA GPU DeepDOC + CPU PaddleOCR
.\install-gpu.ps1
```

사내 embedding endpoint가 없을 때만 기본 설치 완료 후 선택형 CPU 임베딩을 추가합니다.

```powershell
.\install-embedding-cpu.ps1
.\test-embedding.ps1
```

설치 스크립트는 모든 파일의 SHA-256과 Docker 이미지 ID를 검증하고 이미지를 불러온 뒤 `verify-cpu-images.ps1`의 문서 암호·OCR·청킹 기능 검증까지 통과해야 서비스를 시작합니다. 설치 PC에서는 `http://127.0.0.1:42300`, 같은 사내망에서는 `http://<RAG-PC-IP>:42300`으로 접속합니다. 공식 MCP `42303`은 클라이언트 Bearer 없이 연결하고, LIG 관리 MCP `42306`은 서버 `.env.secret` 키를 사용합니다.

반입된 CPU 이미지에 문서 암호·OCR·청킹 수정과 한국어 모델이 실제 포함됐는지는 다음 명령으로 별도 검증할 수 있습니다.

```powershell
.\verify-cpu-images.ps1
```

```powershell
.\start.ps1
.\start-gpu.ps1
.\start-embedding-cpu.ps1
.\stop-embedding.ps1
.\test-embedding.ps1
.\verify-cpu-images.ps1
.\stop.ps1
.\status.ps1
.\diagnostics.ps1
.\diagnostics-gpu.ps1
.\logs.ps1
```

GPU로 설치한 장비는 재부팅 후 반드시 `start-gpu.ps1`을 사용합니다. `install-gpu.ps1`은 GPU 이름·VRAM과 DeepDOC의 CUDA 접근을 확인한 후, 일반 PP-OCRv5는 CPU 서비스로 시작합니다. GPU 스크립트도 `.env.lig`의 공통 기본값인 worker 3개와 worker당 task/parser 슬롯 1개를 그대로 사용하며 별도 강제값은 없습니다. VRAM이 부족할 때만 운영자가 worker 수를 낮춥니다.

`diagnostics.ps1`은 비밀값 없이 서비스 health, task executor heartbeat, 컨테이너 자원 스냅숏, 최근 단계별 처리시간과 오류를 JSON으로 출력합니다. 원격 PaddleX 사용 시에는 task executor·parser 슬롯·페이지 요청 수를 곱한 실효 최대 동시 요청도 함께 표시합니다.

## 한국어 PDF

- 텍스트 선택·복사가 정상: 데이터셋 언어 `Korean`, PDF 파서 `Plain Text`
- 스캔 또는 글꼴 매핑이 깨짐: 데이터셋 언어 `Korean`, 청킹 `Naive`, PDF 파서 `paddleocr-from-env`. 내부 URL, 토큰과 `PP-OCRv5`는 자동 적용되며, 대형 PDF는 고정 기본 `PDF_TASK_PAGE_SIZE=40` 범위만 잘라 OCR 서비스에 전송합니다. 데이터셋 `task_page_size`로 덮어쓸 수 있습니다.
- 영어·중국어 또는 복잡한 표·레이아웃: 기존 `DeepDOC` 유지

`-IncludeGpu -IncludePaddleOcrVl`로 만든 선택 번들에서는 `install-paddleocr-vl.ps1`을 추가 실행할 수 있습니다. 설치 후 모델 목록에 일반 OCR `paddleocr-from-env`와 VL `paddleocr-vl-from-env`가 따로 나타나며, VL은 gateway health가 정상일 때만 활성화됩니다. 12 GiB 기본 구성은 레이아웃 검출을 CPU, 0.9B VLM을 GPU에서 실행하고 vLLM cache 설정을 소형 GPU에 맞춥니다.

일반 PaddleOCR 상태는 `http://127.0.0.1:42316/health`에서 확인합니다. CPU·GPU 설치 모두 응답의 `device`와 `provider`가 `cpu`/`CPUExecutionProvider`여야 합니다. 선택형 VL의 VLM만 GPU를 사용하며 상태는 `42318`에서 별도로 확인합니다.

PDF, Office 및 HWP/HWPX의 파일 열기 비밀번호는 업로드 창에서 파일별로 입력합니다. 최신 Office와 HWPX 암호는 지원하며, 암호화된 바이너리 HWP는 HWPX 또는 DOCX로 다시 저장해야 합니다. 암호 PDF 로그가 `OCR started`까지 진행됐다면 열기 암호는 이미 통과한 것이며, 소유자 암호가 필요한 권한 제한은 OCR 전에 별도 오류로 표시됩니다. 배포용 문서와 IRM/FASOO DRM은 처리하지 않습니다. 저장된 비밀번호 복호화에 필요한 `.env.secret`은 DB와 같은 복구 시점으로 별도 암호화 백업하십시오. 전체 확장자 호환표와 키 회전 절차는 상위 `DOCUMENT-COMPATIBILITY.ko.md`를 따릅니다.

`stop.ps1`은 컨테이너와 네트워크만 정리하며 데이터 볼륨은 삭제하지 않습니다.

## 비밀값과 내부 vLLM

실제 비밀값은 번들에 포함되지 않습니다. 최초 설치 때 `LIG-Deployment\.env.secret.example`을 복사해 `.env.secret`을 자동 생성하고 문서 암호 키, 일반/VL OCR 토큰과 공식 MCP 서버측 키를 각각 만듭니다. 최초 사용자가 생성되면 공식 MCP 키가 첫 테넌트에 자동 등록되므로 클라이언트가 API 키를 보관할 필요가 없습니다.

폐쇄망 내부 vLLM은 RAGFlow 설정에서 OpenAI 호환 공급자로 등록합니다.

- Docker 호스트의 vLLM: `http://host.docker.internal:<포트>/v1`
- 별도 내부 서버의 vLLM: `http://<내부-vllm-IP>:<포트>/v1`

RAGFlow 컨테이너 안에서 접근 가능한 주소여야 하며, 모델명은 vLLM에 로드된 이름과 같아야 합니다. 외부 NVIDIA API는 인터넷이 차단된 폐쇄망에서 사용할 수 없습니다.

## 구성 내용

- `lig/ragflow-ui:v0.26.4-4` 커스텀 UI 이미지
- `lig/ragflow-ui-gpu:v0.26.4-4` CUDA 12.8·cuDNN 9 커스텀 UI 이미지(`-IncludeGpu` 번들만)
- `lig/ragflow-mcp:v0.26.4-3` LIG 관리 MCP 이미지
- `lig/paddleocr-ko:v0.26.4-4` 한국어 PP-OCRv5 CPU 이미지
- `lig/qwen3-embedding-tei:0.6b-1` Qwen3 0.6B 모델 내장 TEI CPU 이미지(`-IncludeEmbedding` 번들만)
- `lig/qwen3-embedding-adapter:0.6b-1` RAGFlow 질의 instruction 어댑터(`-IncludeEmbedding` 번들만)
- 공식 자산 기반 `lig/paddleocr-vl-pipeline-cpu:1.6-1`, 공식 vLLM 오프라인 이미지와 `lig/paddleocr-vl-gateway:1.6-1`(`-IncludePaddleOcrVl` 번들만)
- `infiniflow/ragflow:v0.26.4` 롤백 이미지
- Infinity, MySQL, MinIO, Valkey 이미지
- 고정 버전 Compose 런타임 파일
- 기본 런타임, 선택형 임베딩 및 선택형 PaddleOCR-VL을 분리한 gzip Docker 이미지 아카이브와 SHA-256 manifest

Qwen3 임베딩 이미지와 모델은 내보낼 때 `-IncludeEmbedding`으로 만든 번들에만 포함되며 기본 설치에서는 로드하거나 실행하지 않습니다. 아카이브가 포함되어 있고 사내 embedding endpoint가 없을 때 `install-embedding-cpu.ps1`로 선택 설치합니다. 생성 LLM은 별도로 준비해야 합니다.
