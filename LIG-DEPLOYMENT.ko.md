# LIG RAGFlow 경량 배포

이 구성은 공식 RAGFlow `v0.26.4`를 수정하지 않고 Windows 노트북과 에어갭 환경에서 관리하기 위한 오버레이입니다. 특정 PDF에 종속되지 않으며, 문서 저장·파싱·청킹·검색은 RAGFlow가 담당합니다.

## 선택한 구성

- 문서 엔진: Elasticsearch 대신 Infinity
- 실행 장치: CPU
- 내부 서비스: RAGFlow, Infinity, MySQL, MinIO, Valkey, Ollama
- 임베딩: 다국어 `qwen3-embedding:0.6b`(양자화 모델 약 639 MB)
- 제외: Kibana, Sandbox, TEI, 별도 Docling 서비스
- 포트: 모두 `127.0.0.1`에만 공개
- 웹 UI: `http://127.0.0.1:8080`
- 로그: 컨테이너마다 최대 20 MiB 파일 3개
- 동시 처리: 문서 1개, 임베딩 배치 4개, worker 8개
- 메모리: RAGFlow 5 GiB, Ollama 3 GiB 상한(90쪽 PDF 실측 피크를 반영)

`docker/.env.lig`는 upstream 기본값을 덮어쓰고, `docker/docker-compose.lig.yml`은 메모리와 로그 상한을 추가합니다. 데이터는 공식 named volume에 저장되므로 컨테이너를 다시 만들어도 유지됩니다.

## 실행

PowerShell에서 다음 명령을 사용합니다.

```powershell
cd docker
Copy-Item .env.secret.example .env.secret
# .env.secret의 RAGFLOW_MCP_API_KEY를 RAGFlow UI에서 만든 키로 교체
.\lig-ragflow.ps1 config
.\lig-ragflow.ps1 pull
.\lig-ragflow.ps1 start
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

RAGFlow `v0.22` 이후 기본 이미지는 임베딩 모델을 포함하지 않습니다. 이 프로필은 Ollama와 다국어 `qwen3-embedding:0.6b`를 사용합니다. Ollama 모델은 약 639 MB이고 100개 이상 언어 및 32K 문맥을 지원해 한국어 문서 시험에 적합합니다. 16 GB 노트북에는 공식 TEI 기본 Qwen3 0.6B(약 25 GB RAM 요구)나 BGE-M3(약 21 GB)가 맞지 않아 TEI는 제외했습니다.

에어갭 반입 시에는 compose에 사용되는 모든 Docker 이미지를 인터넷 환경에서 `docker save`로 내보내고, 폐쇄망에서 `docker load`로 복원합니다. `ollama_data` 볼륨의 모델도 별도로 백업·복원해야 합니다. 모델은 범용이며 문서나 PDF마다 다시 받지 않습니다.

온라인 PC에서 반입 묶음을 만들고 폐쇄망 PC에서 복원하는 명령은 다음과 같습니다. 내보내기 폴더에는 6개 고정 버전 이미지, Ollama 모델, SHA-256 manifest가 생성됩니다. `.env.secret`은 보안상 묶음에 포함하지 않으므로 폐쇄망에서 별도로 작성합니다.

```powershell
.\airgap-export.ps1 -Destination D:\LIG-RAGFlow-Airgap
.\airgap-import.ps1 -Source D:\LIG-RAGFlow-Airgap
```

RAGFlow의 Ollama 공급자에는 base URL `http://ollama:11434`, 모델명 `qwen3-embedding:0.6b`, 유형 `Embedding`을 등록합니다. 호스트 브라우저나 진단 도구에서는 `http://127.0.0.1:11434`로 접근합니다.

## MCP 범위

RAGFlow 기본 MCP는 검색과 데이터셋·채팅 목록 조회에 집중합니다. `.env.secret`에 API 키가 있으면 이 배포는 공식 MCP를 `http://127.0.0.1:9382/mcp`에 함께 시작합니다. 데이터셋과 문서의 생성·수정·삭제는 상위 폴더의 `RAGFlow-MCP-LIG` 관리 어댑터가 담당합니다. API 키를 만든 뒤 두 MCP를 함께 연결하는 것이 최종 구성입니다.
