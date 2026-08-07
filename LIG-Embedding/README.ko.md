# Qwen3 임베딩 선택 설치

RAGFlow의 기본 설치와 분리된 CPU 임베딩 서비스입니다. `Qwen/Qwen3-Embedding-0.6B`를 Hugging Face Text Embeddings Inference(TEI) 1.9로 제공하며, 모델 파일은 Docker 이미지에 포함되어 실행 시 인터넷을 사용하지 않습니다.

- 모델: `Qwen/Qwen3-Embedding-0.6B`
- 모델 리비전: `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`
- 모델 파일 SHA-256: `0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd`
- 런타임: TEI `cpu-1.9`
- 벡터 차원: 1024
- 모델 라이선스: Apache-2.0
- 로컬 상태 포트: `http://127.0.0.1:42317/health`
- Compose 내부 Base URL: `http://qwen3-embedding:8080`
- 요청당 최대 토큰: 2,048(초과 입력 자동 절단)

어댑터는 RAGFlow가 단일 문자열로 보내는 검색 질의에만 Qwen 권장 형식의 검색 지시문을 추가합니다. 배열로 보내는 문서 청크는 변경하지 않습니다. RAGFlow 원본 코드는 수정하지 않습니다.

CPU 추론의 배치 크기는 `.env.lig`의 `EMBEDDING_BATCH_SIZE`로 조정합니다. RAGFlow의 HuggingFace 공급자 요청 제한시간은 `HUGGINGFACE_EMBEDDING_TIMEOUT_SECONDS`, 어댑터에서 TEI로 향하는 제한시간은 `EMBEDDING_UPSTREAM_TIMEOUT_SECONDS`로 조정할 수 있으며 둘 다 기본값은 300초입니다. 어댑터는 `EMBEDDING_MAX_CONCURRENT_REQUESTS`개까지 TEI로 동시에 전달하고 나머지는 거부하지 않고 대기시켜 CPU 백엔드 큐 고갈과 재시작을 방지합니다. 어댑터는 문서 처리와 사용자 검색 질의를 함께 받으므로 이 값이 1이면 검색이 처리 중인 배치 뒤에서 대기합니다. 기본값 6은 문서 처리가 쓰는 `MAX_CONCURRENT_EMBEDDERS=4`보다 2 큰 값이며, 그 여유분이 검색 질의용 슬롯입니다. TEI 자체의 `--max-concurrent-requests 8`이 상한이고 이 값은 올리지 마십시오. 16으로 올려 측정했을 때 동시성 4의 소요가 11.36초에서 96.95초로 늘었습니다. `/health`의 `requests` 항목에서 대기·진행 중 요청, 성공·실패·클라이언트 연결 종료 및 최근 요청 시간을 확인할 수 있습니다.

로컬 개발 배포에서는 다음 명령으로 이미지를 빌드한 뒤 선택형 서비스를 시작합니다.

```powershell
.\LIG-Deployment\lig-ragflow.ps1 embedding-build
.\LIG-Deployment\lig-ragflow.ps1 embedding-start
```

중지는 `embedding-stop`, 상태와 실제 벡터 검증은 각각 `embedding-status`, `embedding-test`를 사용합니다.
