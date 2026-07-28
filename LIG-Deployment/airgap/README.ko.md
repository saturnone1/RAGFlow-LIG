# LIG AI Knowledge Hub 에어갭 설치

이 폴더만 폐쇄망 Windows PC로 복사하면 됩니다. 인터넷 연결이나 원본 Git 저장소는 필요하지 않습니다.

상세 설치, API 키, 포트, 내부 vLLM 생성/embedding 모델 등록, 운영 및 백업 절차는 `INSTALL-AND-CONFIGURATION.ko.md`를 먼저 읽으십시오.

## 준비 사항

- Windows 10/11과 Docker Desktop(Compose v2 포함)
- C 드라이브 여유 공간 최소 20 GiB
- `42300`~`42317`의 `.env.lig` 지정 로컬 포트가 비어 있어야 함
- GPU 설치: NVIDIA GPU, 최신 드라이버, Docker의 NVIDIA Container Toolkit/GPU 접근, Docker 메모리 20 GiB 이상 권장

## 설치와 운영

Docker Desktop을 시작한 뒤 이 폴더에서 PowerShell을 열고 실행합니다.

```powershell
# CPU DeepDoc
.\install.ps1

# NVIDIA GPU DeepDOC + PaddleOCR
.\install-gpu.ps1
```

사내 embedding endpoint가 없을 때만 기본 설치 완료 후 선택형 CPU 임베딩을 추가합니다.

```powershell
.\install-embedding-cpu.ps1
.\test-embedding.ps1
```

설치 스크립트는 모든 파일의 SHA-256과 Docker 이미지 ID를 검증하고 이미지를 불러온 다음 서비스를 시작합니다. 설치가 끝나면 `http://127.0.0.1:42300`으로 접속합니다. 공식 MCP는 `42303`, LIG 관리 MCP는 `42306`입니다.

```powershell
.\start.ps1
.\start-gpu.ps1
.\start-embedding-cpu.ps1
.\stop-embedding.ps1
.\test-embedding.ps1
.\stop.ps1
.\status.ps1
.\diagnostics.ps1
.\diagnostics-gpu.ps1
.\logs.ps1
```

GPU로 설치한 장비는 재부팅 후 반드시 `start-gpu.ps1`을 사용합니다. `install-gpu.ps1`은 RAGFlow와 PaddleOCR 이미지를 실제 `--gpus all` 컨테이너로 실행해 DeepDOC와 PaddleOCR의 CUDA 접근, GPU 이름·VRAM을 확인한 후 서비스를 시작합니다. 12 GiB VRAM 장비에서는 모델 중복 적재를 피하기 위해 task executor 1개를 기본으로 사용합니다.

`diagnostics.ps1`은 비밀값 없이 서비스 health, task executor heartbeat, 컨테이너 자원 스냅숏, 최근 단계별 처리시간과 오류를 JSON으로 출력합니다.

## 한국어 PDF

- 텍스트 선택·복사가 정상: 데이터셋 언어 `Korean`, PDF 파서 `Plain Text`
- 스캔 또는 글꼴 매핑이 깨짐: 데이터셋 언어 `Korean`, 청킹 `Naive`, PDF 파서 `paddleocr-from-env`. 내부 URL, 토큰과 `PP-OCRv5`는 자동 적용되므로 별도로 입력하지 않습니다.
- 영어·중국어 또는 복잡한 표·레이아웃: 기존 `DeepDOC` 유지

PaddleOCR 상태는 `http://127.0.0.1:42316/health`에서 확인합니다. CPU 설치는 ONNX Runtime CPU, GPU 설치는 CUDA를 사용하며 모델은 이미지에 선탑재되어 있습니다.

PDF, Office 및 HWP/HWPX의 파일 열기 비밀번호는 업로드 창에서 파일별로 입력합니다. 최신 Office와 HWPX 암호는 지원하며, 암호화된 바이너리 HWP는 HWPX 또는 DOCX로 다시 저장해야 합니다. 배포용 문서와 IRM/FASOO DRM은 처리하지 않습니다. 저장된 비밀번호 복호화에 필요한 `.env.secret`은 반드시 별도로 백업하십시오.

`stop.ps1`은 컨테이너와 네트워크만 정리하며 데이터 볼륨은 삭제하지 않습니다.

## 비밀값과 내부 vLLM

실제 비밀값은 번들에 포함되지 않습니다. 최초 설치 때 `LIG-Deployment\.env.secret.example`을 복사해 `.env.secret`을 자동 생성합니다. RAGFlow UI에서 API 키를 만든 후 자리표시자 값을 교체하고 `stop.ps1`, `start.ps1` 순서로 재시작하십시오.

폐쇄망 내부 vLLM은 RAGFlow 설정에서 OpenAI 호환 공급자로 등록합니다.

- Docker 호스트의 vLLM: `http://host.docker.internal:<포트>/v1`
- 별도 내부 서버의 vLLM: `http://<내부-vllm-IP>:<포트>/v1`

RAGFlow 컨테이너 안에서 접근 가능한 주소여야 하며, 모델명은 vLLM에 로드된 이름과 같아야 합니다. 외부 NVIDIA API는 인터넷이 차단된 폐쇄망에서 사용할 수 없습니다.

## 구성 내용

- `lig/ragflow-ui:v0.26.4-1` 커스텀 UI 이미지
- `lig/ragflow-ui-gpu:v0.26.4-1` CUDA 12.8·cuDNN 9 커스텀 UI 이미지
- `lig/ragflow-mcp:v0.26.4-1` LIG 관리 MCP 이미지
- `lig/paddleocr-ko:v0.26.4-1` 한국어 PP-OCRv5 CPU 이미지
- `lig/paddleocr-ko-gpu:v0.26.4-1` 한국어 PP-OCRv5 CUDA 이미지
- `lig/qwen3-embedding-tei:0.6b-1` Qwen3 0.6B 모델 내장 TEI CPU 이미지
- `lig/qwen3-embedding-adapter:0.6b-1` RAGFlow 질의 instruction 어댑터
- `infiniflow/ragflow:v0.26.4` 롤백 이미지
- Infinity, MySQL, MinIO, Valkey 이미지
- 고정 버전 Compose 런타임 파일
- 기본 런타임과 선택형 임베딩을 분리한 gzip Docker 이미지 아카이브 및 SHA-256 manifest

Qwen3 임베딩 이미지와 모델은 번들 폴더에 포함되지만 기본 설치에서는 로드하거나 실행하지 않습니다. 사내 embedding endpoint가 없을 때 `install-embedding-cpu.ps1`로 선택 설치합니다. 생성 LLM은 별도로 준비해야 합니다.
