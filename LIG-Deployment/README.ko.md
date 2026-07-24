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
- 동시 처리: 문서 1개, 임베딩 배치 4개, worker 8개
- 메모리: RAGFlow 5 GiB 상한. Ollama 선택 프로필을 사용할 때만 Ollama에 3 GiB 상한 적용

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
.\lig-ragflow.ps1 logs
```

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
