# LIG AI Knowledge Hub 에어갭 설치

이 폴더만 폐쇄망 Windows PC로 복사하면 됩니다. 인터넷 연결이나 원본 Git 저장소는 필요하지 않습니다.

## 준비 사항

- Windows 10/11과 Docker Desktop(Compose v2 포함)
- C 드라이브 여유 공간 최소 20 GiB
- `42200`~`42215`의 `.env.lig` 지정 로컬 포트가 비어 있어야 함

## 설치와 운영

Docker Desktop을 시작한 뒤 이 폴더에서 PowerShell을 열고 실행합니다.

```powershell
.\install.ps1
```

설치 스크립트는 모든 파일의 SHA-256을 검증하고, Docker 이미지를 불러온 다음 서비스를 시작합니다. 설치가 끝나면 `http://127.0.0.1:42200`으로 접속합니다. 공식 MCP는 `42203`, LIG 관리 MCP는 `42206`입니다.

```powershell
.\start.ps1
.\stop.ps1
.\status.ps1
.\logs.ps1
```

`stop.ps1`은 컨테이너와 네트워크만 정리하며 데이터 볼륨은 삭제하지 않습니다.

## 비밀값과 내부 vLLM

실제 비밀값은 번들에 포함되지 않습니다. 최초 설치 때 `LIG-Deployment\.env.secret.example`을 복사해 `.env.secret`을 자동 생성합니다. RAGFlow UI에서 API 키를 만든 후 자리표시자 값을 교체하고 `stop.ps1`, `start.ps1` 순서로 재시작하십시오.

폐쇄망 내부 vLLM은 RAGFlow 설정에서 OpenAI 호환 공급자로 등록합니다.

- Docker 호스트의 vLLM: `http://host.docker.internal:<포트>/v1`
- 별도 내부 서버의 vLLM: `http://<내부-vllm-IP>:<포트>/v1`

RAGFlow 컨테이너 안에서 접근 가능한 주소여야 하며, 모델명은 vLLM에 로드된 이름과 같아야 합니다. 외부 NVIDIA API는 인터넷이 차단된 폐쇄망에서 사용할 수 없습니다.

## 구성 내용

- `lig/ragflow-ui:v0.26.4-1` 커스텀 UI 이미지
- `lig/ragflow-mcp:v0.26.4-1` LIG 관리 MCP 이미지
- `infiniflow/ragflow:v0.26.4` 롤백 이미지
- Infinity, MySQL, MinIO, Valkey 이미지
- 고정 버전 Compose 런타임 파일
- gzip으로 압축된 Docker 이미지 아카이브와 SHA-256 manifest
- Ollama 이미지와 모델은 `-IncludeOllama`로 내보낸 번들에만 포함
