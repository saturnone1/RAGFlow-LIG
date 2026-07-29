# LIG AI Knowledge Hub UI

공식 RAGFlow v0.26.4의 `RAGFlow/` 원본은 수정하지 않습니다. 프런트엔드 화이트라벨 결과를 덧씌우고, 최종 이미지에는 `LIG-Runtime/`의 버전 고정 패치로 HuggingFace 임베딩 60초 제한, PaddleOCR 종료 진행률, 배치 임베딩 진행률 계산만 적용합니다.

## 빌드

저장소 루트에서 실행합니다.

```powershell
docker build -f LIG-UI/Dockerfile -t lig/ragflow-ui:v0.26.4-2 .
```

또는 배포 도우미를 사용합니다.

```powershell
.\LIG-Deployment\lig-ragflow.ps1 ui-build
```

GPU 전용 이미지는 CPU UI 이미지 위에 ONNX Runtime 1.23.2용 CUDA 12.8·cuDNN 9 라이브러리를 고정 버전으로 추가합니다. GPU RAGFlow와 PaddleOCR 이미지를 함께 빌드하려면 CPU UI와 OCR 빌드 후 다음 명령을 실행합니다.

```powershell
.\LIG-Deployment\lig-ragflow.ps1 gpu-build
```

빌드는 대상 RAGFlow 프런트와 런타임 파일의 SHA-256을 검사합니다. 업스트림 버전이 바뀌면 오버레이와 런타임 패치를 재검토하기 전까지 실패하는 것이 정상입니다.

업스트림 v0.26.4 전체 `type-check`와 전체 ESLint에는 기존 오류가 있습니다. 빌드는 공식 오류 집합을 기준선으로 기록한 뒤 오버레이가 새 TypeScript 오류를 추가하면 실패합니다. LIG 추가 파일의 ESLint, 데이터셋 설정 회귀 테스트와 production Vite 빌드도 모두 통과해야 하며 Node와 최종 RAGFlow 베이스 이미지는 digest로 고정합니다.

## 구조

- `overlay/`: 임시 프런트 복사본에 추가·교체되는 브랜드 코드와 자산
- `scripts/apply-overlay.mjs`: 버전 검증 및 최소 텍스트 변환
- `../LIG-Runtime/apply-runtime-patches.py`: 공식 이미지에만 적용되는 버전 고정 런타임 패치
- `assets-manifest.json`: 공식 자산의 출처, 다운로드 시점과 SHA-256
- `Dockerfile`: 공식 이미지 위에 브랜드 `web/dist`와 제한된 런타임 패치를 적용하는 빌드
- `Dockerfile.gpu`: CPU UI 이미지 위에 고정된 CUDA 12.8·cuDNN 9 사용자 공간 런타임을 추가하는 빌드

원복은 `LIG-Deployment/.env.lig`의 `RAGFLOW_IMAGE`를 공식 `infiniflow/ragflow:v0.26.4`로 되돌린 뒤 컨테이너를 다시 시작하면 됩니다.
