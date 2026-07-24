# LIG AI Knowledge Hub UI

공식 RAGFlow v0.26.4의 백엔드는 그대로 두고 프런트엔드 빌드 결과만 화이트라벨하는 오버레이입니다. `RAGFlow/` 아래 파일은 수정하지 않습니다.

## 빌드

저장소 루트에서 실행합니다.

```powershell
docker build -f LIG-UI/Dockerfile -t lig/ragflow-ui:v0.26.4-1 .
```

또는 배포 도우미를 사용합니다.

```powershell
.\LIG-Deployment\lig-ragflow.ps1 ui-build
```

빌드는 대상 RAGFlow 프런트 파일의 SHA-256을 검사합니다. 업스트림 버전이 바뀌면 오버레이를 재검토하기 전까지 실패하는 것이 정상입니다.

업스트림 v0.26.4 전체 `type-check`와 전체 ESLint에는 기존 오류가 있으므로, 화이트라벨 검증은 오버레이 대상 파일 ESLint와 production Vite 빌드를 기준으로 합니다.

## 구조

- `overlay/`: 임시 프런트 복사본에 추가·교체되는 브랜드 코드와 자산
- `scripts/apply-overlay.mjs`: 버전 검증 및 최소 텍스트 변환
- `assets-manifest.json`: 공식 자산의 출처, 다운로드 시점과 SHA-256
- `Dockerfile`: 공식 이미지 위에 브랜드 `web/dist`만 교체하는 빌드

원복은 `LIG-Deployment/.env.lig`의 `RAGFLOW_IMAGE`를 공식 `infiniflow/ragflow:v0.26.4`로 되돌린 뒤 컨테이너를 다시 시작하면 됩니다.
