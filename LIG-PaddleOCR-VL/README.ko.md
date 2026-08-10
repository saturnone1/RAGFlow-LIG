# LIG PaddleOCR-VL 호환 게이트웨이

공식 PaddleOCR-VL-1.6 pipeline API를 RAGFlow의 비동기 OCR 작업 API와 연결합니다. 모델 추론은 공식 오프라인 GPU 이미지에서 수행하며, 이 게이트웨이는 작업 제출·상태 조회·취소·결과 다운로드 형식만 기존 `paddleocr-from-env`와 같게 맞춥니다.

이 구성은 선택 설치 항목입니다. `LIG-Deployment/lig-ragflow.ps1 paddleocr-vl-build`로 게이트웨이를 빌드하고 `paddleocr-vl-start`로 시작합니다. RAGFlow 설정에서는 `paddleocr-vl-from-env`를 선택합니다.
