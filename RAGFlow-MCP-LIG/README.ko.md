# LIG RAGFlow 관리 MCP

이 서버는 AI 에이전트가 MCP를 통해 RAGFlow의 데이터셋, 문서, 파싱 작업, 청크를 관리하도록 연결하는 어댑터입니다. 문서 파싱·OCR·레이아웃 분석·청킹·임베딩·검색 엔진을 다시 구현하지 않고 RAGFlow 공식 REST API를 호출합니다. 특정 PDF, 파일명 또는 데이터셋에 종속되지 않습니다.

RAGFlow에 포함된 공식 MCP는 검색과 조회에 집중합니다. 이 관리 MCP는 등록·수정·삭제를 포함한 운영 기능을 보완합니다. 일반적인 구성은 다음과 같습니다.

1. 에이전트가 이 관리 MCP로 데이터셋과 문서를 등록하고 파싱을 시작합니다.
2. RAGFlow가 원본을 보관하고 OCR, 구조 분석, 청킹, 임베딩, 인덱싱을 수행합니다.
3. 에이전트는 RAGFlow 공식 MCP로 완성된 지식베이스를 검색합니다.
4. 수정·재처리·삭제가 필요하면 다시 이 관리 MCP를 호출합니다.

## 제공 도구

- `rag_flow_config`: 연결 상태와 쓰기 허용 여부 확인
- `list_rag_flow_datasets`, `create_rag_flow_dataset`, `update_rag_flow_dataset`, `delete_rag_flow_dataset`
- `list_rag_flow_documents`, `upload_rag_flow_document`, `update_rag_flow_document`, `delete_rag_flow_documents`
- `start_rag_flow_parsing`, `stop_rag_flow_parsing`
- `list_rag_flow_chunks`, `create_rag_flow_chunk`, `update_rag_flow_chunk`, `delete_rag_flow_chunks`
- `rag_flow_api_catalog`: 데이터셋, 채팅, 에이전트, 메모리, 파일, 검색 앱, 모델·공급자, MCP·커넥터, 팀·시스템 API 경로 안내
- `rag_flow_api_request`: 모든 비스트리밍 `/api/v1` JSON·텍스트 API 호출
- `upload_rag_flow_api_files`: 모든 `/api/v1` multipart 업로드 API 호출
- `download_rag_flow_api_response`: 문서·첨부·음성 등 바이너리 API 응답 저장

기존 15개 도구는 자주 쓰는 데이터셋 작업을 간단한 매개변수로 제공하는 편의 도구입니다. 추가된 4개 범용 도구는 RAGFlow v0.26.4의 REST 표면 전체를 제공하므로 채팅·세션, 에이전트, 검색, 메모리, 파일, 모델, 공급자, 기본 모델, MCP 서버, 커넥터, 팀과 시스템 설정도 MCP에서 사용할 수 있습니다. RAGFlow에 새 `/api/v1` 엔드포인트가 추가되어도 어댑터 코드를 다시 작성할 필요가 없습니다.

예를 들어 등록 모델과 시스템 상태를 조회하려면 에이전트가 다음 인수로 `rag_flow_api_request`를 호출합니다.

```json
{"method":"GET","relativePath":"api/v1/models"}
```

```json
{"method":"GET","relativePath":"api/v1/system/status"}
```

JSON 본문이 필요한 API는 문자열 형태의 `bodyJson`을 전달합니다.

```json
{
  "method": "PATCH",
  "relativePath": "api/v1/models/default",
  "bodyJson": "{\"model_type\":\"embedding\",\"model_name\":\"internal-vllm-model\"}"
}
```

범용 도구는 임의 외부 URL과 HTTP 리다이렉트를 따라가지 않습니다. `api/v1/`로 시작하는 상대 경로만 허용하며, GET·HEAD 이외 요청과 업로드는 `RAGFLOW_WRITES_ENABLED=true`일 때만 실행합니다. 로컬 다운로드는 별도로 `RAGFLOW_FILE_WRITES_ENABLED=true`가 필요하고, 기존 파일을 기본적으로 덮어쓰지 않습니다. JSON 다운로드도 RAGFlow의 `code`를 검사한 후 임시 파일을 원자적으로 이동하므로 오류 응답이나 중단된 응답이 목적지 파일로 남지 않습니다.

MCP 도구 결과는 단일 응답이므로 SSE를 실시간 중계하지 않습니다. 채팅·에이전트 completion API는 요청 본문에 `"stream":false`를 지정하십시오. 실시간 토큰 스트리밍이 필요하면 해당 RAGFlow API를 직접 호출해야 합니다. JSON·텍스트 결과는 기본 4 MiB로 제한하며 `RAGFLOW_MAX_TEXT_RESPONSE_MB`로 1~64 MiB 범위에서 조정할 수 있습니다.

삭제 도구는 RAGFlow가 연결된 원본 저장소와 인덱스도 변경합니다. 읽기 전용 운용이 필요하면 `RAGFLOW_WRITES_ENABLED=false`로 시작하십시오.

## 실행 환경

- LIG 배포의 RAGFlow API: `http://127.0.0.1:42301`
- Compose 관리 MCP Streamable HTTP: `http://127.0.0.1:42306/mcp`
- Compose 상태 확인: `http://127.0.0.1:42306/healthz`
- 소스 빌드: .NET 8 SDK 이상
- 자체 포함 배포본: 별도 .NET 런타임 불필요

RAGFlow UI의 사용자 설정/API 메뉴에서 API 키를 만든 뒤 현재 PowerShell 세션에만 전달합니다. 키를 소스, Compose 파일 또는 MCP 클라이언트가 공유하는 저장소에 기록하지 마십시오.

```powershell
$env:RAGFLOW_BASE_URL='http://127.0.0.1:42301'
$env:RAGFLOW_API_KEY='ragflow-...'
$env:RAGFLOW_WRITES_ENABLED='true'
dotnet run --project src/RagFlowMcp.csproj
```

기본 LIG 배포에서는 이 MCP가 `lig/ragflow-mcp:v0.26.4-2` 컨테이너로 RAGFlow와 함께 시작·중지됩니다. 다음 명령으로 두 커스텀 이미지를 만들고 전체 구성을 실행합니다.

```powershell
cd ..\LIG-Deployment
.\lig-ragflow.ps1 build
.\lig-ragflow.ps1 start
```

컨테이너는 CPU/GPU 설치에서 공통으로 유지되는 RAGFlow 내부 별칭 `http://ragflow-runtime:9380`을 사용하며, 호스트에는 관리 MCP만 `127.0.0.1:42306`으로 공개합니다. 업로드할 파일은 `LIG-Deployment/mcp-files`에 넣고 MCP 도구에는 `/data/<파일명>`을 전달합니다.

Docker 없이 개발할 때만 저장소의 `LIG-Deployment/.env.secret`을 읽는 Windows 백그라운드 실행 스크립트를 사용합니다.

```powershell
.\start-lig-ragflow-mcp.ps1
# 실행 중인 프로세스를 새 빌드로 교체
.\start-lig-ragflow-mcp.ps1 -Restart
# RAGFlow 변경을 막는 읽기 전용 실행
.\start-lig-ragflow-mcp.ps1 -Restart -ReadOnly
# 로컬 파일 다운로드도 필요한 경우에만 명시적으로 허용
.\start-lig-ragflow-mcp.ps1 -Restart -EnableFileDownloads
```

자체 포함 Windows 배포본은 다음 명령으로 만듭니다.

```powershell
dotnet publish src/RagFlowMcp.csproj -c Release -r win-x64 --self-contained true -o publish/win-x64
.\publish\win-x64\LigRagFlowMcp.exe
```

## MCP 클라이언트 연결

Compose 관리 MCP를 사용하는 클라이언트에는 `http://127.0.0.1:42306/mcp`를 등록합니다. Compose 배포는 `.env.secret`의 `RAGFLOW_MCP_API_KEY`를 관리 MCP의 Bearer 키로도 사용하므로 클라이언트가 `Authorization: Bearer <RAGFLOW_MCP_API_KEY>` 헤더를 보내야 합니다. 호스트 포트는 로컬 PC에만 바인딩됩니다. Docker 없이 시작 스크립트로 실행한 개발 인스턴스는 충돌 방지를 위해 기존 `http://127.0.0.1:42206/mcp`를 사용합니다. 별도 실행에서 `ASPNETCORE_URLS`를 외부 인터페이스에 바인딩하려면 `LIG_MCP_API_KEY`가 반드시 설정되어야 합니다. `/healthz`에는 비밀 정보가 없으며 인증 없이 상태 확인에 사용할 수 있습니다.

환경변수는 다음과 같습니다.

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `RAGFLOW_BASE_URL` | `http://127.0.0.1:42301` | RAGFlow REST API 주소. Compose 내부에서는 `http://ragflow-runtime:9380` |
| `RAGFLOW_API_KEY` | 없음 | RAGFlow API 키, 필수 |
| `RAGFLOW_WRITES_ENABLED` | `false` | `true`일 때만 생성·수정·삭제·파싱 허용. 시작 스크립트는 기존 운용 호환을 위해 기본 `true`, `-ReadOnly`로 차단 |
| `RAGFLOW_FILE_WRITES_ENABLED` | `false` | `true`일 때만 다운로드 도구의 로컬 파일 생성·덮어쓰기 허용 |
| `RAGFLOW_MAX_TEXT_RESPONSE_MB` | `4` | 범용 JSON·텍스트 응답 상한, 1~64 MiB |
| `LIG_MCP_API_KEY` | 없음 | MCP 호출용 별도 Bearer 키. 외부 인터페이스 바인딩 시 필수 |
| `ASPNETCORE_URLS` | `http://127.0.0.1:42206` | Docker 없이 실행하는 개발 MCP 수신 주소. Compose는 호스트 `42306`을 컨테이너 `8080`에 연결 |

`upload_rag_flow_document`의 `filePath`는 MCP 프로세스가 실제로 읽을 수 있어야 합니다. Compose 배포에서는 `LIG-Deployment/mcp-files`가 컨테이너의 `/data`로 연결되므로 `/data/<파일명>`을 사용합니다. Windows 직접 실행에서는 접근 가능한 로컬 절대 경로를 사용할 수 있습니다.

## 검증

조회 연결, 19개 도구 노출, MCP 무인증 요청 차단, API 카탈로그, 범용 시스템 버전·모델 API 호출, 다운로드 크기와 JSON 성공 코드를 확인합니다.

```powershell
$env:RAGFLOW_API_KEY='ragflow-...'
.\tests\mcp-smoke.ps1
```

Compose에서 실행 중인 관리 MCP와 컨테이너 내부 RAGFlow 연결을 확인하려면 다음 명령을 사용합니다.

```powershell
$env:RAGFLOW_API_KEY='ragflow-...'
.\tests\mcp-compose-smoke.ps1
```

임시 데이터셋 생성부터 업로드, 파싱, 청크 수정·삭제, 정리까지 확인하려면 다음처럼 실행합니다. 실행 중인 대형 파싱 작업이 있으면 RAGFlow 작업 큐 때문에 시간이 더 걸릴 수 있습니다.

청킹 없이 범용 multipart 업로드와 삭제만 확인하려면 다음 명령을 사용합니다. 테스트 파일은 성공·실패와 관계없이 정리합니다.

```powershell
.\tests\mcp-smoke.ps1 -GenericUpload
```

```powershell
.\tests\mcp-smoke.ps1 -Crud
```

테스트는 성공 여부와 도구 수만 출력하며 API 키를 출력하지 않습니다. CRUD 테스트에서 만든 데이터셋은 성공·실패와 관계없이 마지막 정리 단계에서 삭제합니다.

## 에어갭 운용

이 실행 파일만으로 RAG 기능이 생기는 것은 아닙니다. 에어갭 PC에는 RAGFlow Docker 이미지, Ollama 임베딩 모델, RAGFlow 데이터 볼륨이 필요합니다. 온라인 PC에서 `LIG-Deployment/airgap-export.ps1`로 반입 묶음을 만들고 오프라인 PC에서 `airgap-import.ps1`로 복원한 다음 RAGFlow를 먼저 시작하십시오.

API 키는 반입 묶음에 포함하지 않습니다. 오프라인 RAGFlow UI에서 새로 만들고 이 MCP 프로세스의 환경변수로 전달합니다. 임베딩 모델은 특정 PDF 전용 데이터가 아니라 모든 문서에 재사용하는 범용 모델입니다.
