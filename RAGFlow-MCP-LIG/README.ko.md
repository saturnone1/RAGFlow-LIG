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

삭제 도구는 RAGFlow가 연결된 원본 저장소와 인덱스도 변경합니다. 읽기 전용 운용이 필요하면 `RAGFLOW_WRITES_ENABLED=false`로 시작하십시오.

## 실행 환경

- LIG 배포의 RAGFlow API: `http://127.0.0.1:19380`
- MCP Streamable HTTP: 기본값 `http://127.0.0.1:42220/mcp`
- 상태 확인: `http://127.0.0.1:42220/healthz`
- 소스 빌드: .NET 8 SDK 이상
- 자체 포함 배포본: 별도 .NET 런타임 불필요

RAGFlow UI의 사용자 설정/API 메뉴에서 API 키를 만든 뒤 현재 PowerShell 세션에만 전달합니다. 키를 소스, Compose 파일 또는 MCP 클라이언트가 공유하는 저장소에 기록하지 마십시오.

```powershell
$env:RAGFLOW_BASE_URL='http://127.0.0.1:19380'
$env:RAGFLOW_API_KEY='ragflow-...'
$env:RAGFLOW_WRITES_ENABLED='true'
dotnet run --project src/RagFlowMcp.csproj
```

LIG 로컬 배포에서는 저장소의 `LIG-Deployment/.env.secret`을 읽어 관리 MCP를 백그라운드로 시작하는 스크립트를 사용할 수 있습니다.

```powershell
.\start-lig-ragflow-mcp.ps1
# 실행 중인 프로세스를 새 빌드로 교체
.\start-lig-ragflow-mcp.ps1 -Restart
```

자체 포함 Windows 배포본은 다음 명령으로 만듭니다.

```powershell
dotnet publish src/RagFlowMcp.csproj -c Release -r win-x64 --self-contained true -o publish/win-x64
.\publish\win-x64\LigRagFlowMcp.exe
```

## MCP 클라이언트 연결

Streamable HTTP를 지원하는 클라이언트에는 `http://127.0.0.1:42220/mcp`를 등록합니다. 서버를 다른 PC에서 사용하려면 `ASPNETCORE_URLS`의 바인딩 주소와 방화벽을 별도로 설정해야 합니다. 기본값은 로컬 PC 전용입니다.

환경변수는 다음과 같습니다.

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `RAGFLOW_BASE_URL` | `http://127.0.0.1:19380` | RAGFlow REST API 주소 |
| `RAGFLOW_API_KEY` | 없음 | RAGFlow API 키, 필수 |
| `RAGFLOW_WRITES_ENABLED` | `true` | `false`이면 생성·수정·삭제·파싱 제어 차단 |
| `ASPNETCORE_URLS` | `http://127.0.0.1:42220` | 관리 MCP 수신 주소 |

`upload_rag_flow_document`의 `filePath`는 MCP 프로세스가 실제로 읽을 수 있는 로컬 절대 경로여야 합니다. C, D 등 드라이브 문자는 제한하지 않으며 실행 계정의 Windows 파일 권한만 적용됩니다.

## 검증

조회 연결과 15개 도구 노출을 확인합니다.

```powershell
$env:RAGFLOW_API_KEY='ragflow-...'
.\tests\mcp-smoke.ps1
```

임시 데이터셋 생성부터 업로드, 파싱, 청크 수정·삭제, 정리까지 확인하려면 다음처럼 실행합니다. 실행 중인 대형 파싱 작업이 있으면 RAGFlow 작업 큐 때문에 시간이 더 걸릴 수 있습니다.

```powershell
.\tests\mcp-smoke.ps1 -Crud
```

테스트는 성공 여부와 도구 수만 출력하며 API 키를 출력하지 않습니다. CRUD 테스트에서 만든 데이터셋은 성공·실패와 관계없이 마지막 정리 단계에서 삭제합니다.

## 에어갭 운용

이 실행 파일만으로 RAG 기능이 생기는 것은 아닙니다. 에어갭 PC에는 RAGFlow Docker 이미지, Ollama 임베딩 모델, RAGFlow 데이터 볼륨이 필요합니다. 온라인 PC에서 `LIG-Deployment/airgap-export.ps1`로 반입 묶음을 만들고 오프라인 PC에서 `airgap-import.ps1`로 복원한 다음 RAGFlow를 먼저 시작하십시오.

API 키는 반입 묶음에 포함하지 않습니다. 오프라인 RAGFlow UI에서 새로 만들고 이 MCP 프로세스의 환경변수로 전달합니다. 임베딩 모델은 특정 PDF 전용 데이터가 아니라 모든 문서에 재사용하는 범용 모델입니다.
