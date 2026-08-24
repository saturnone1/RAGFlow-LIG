# LIG PaddleOCR-VL 호환 게이트웨이

공식 PaddleOCR-VL-1.6 pipeline API를 RAGFlow의 비동기 OCR 작업 API와 연결합니다. 공식 오프라인 pipeline 이미지의 모델 자산과 PaddleOCR/PaddleX는 유지하고 CUDA에 링크된 `paddlepaddle-gpu 3.2.1`만 동일 버전 CPU 패키지로 교체합니다. 따라서 pipeline 컨테이너는 GPU 장치 전달 없이 실행됩니다. 12 GiB 기본 구성은 일반 PP-OCRv5와 레이아웃 검출을 CPU에서 실행하고 0.9B VLM만 PaddleOCR 계열 GPU 작업으로 실행합니다. vLLM은 eager 모드, GPU 메모리 비율 0.60, API server 1개와 batch tokens 16,384를 사용해 소형 GPU의 KV cache 기동 실패를 줄입니다. 게이트웨이는 작업 제출·상태 조회·취소·결과 다운로드 형식만 기존 PaddleOCR와 같게 맞춥니다.

이 구성은 선택 설치 항목입니다. `LIG-Deployment/lig-ragflow.ps1 paddleocr-vl-pull`로 공식 기반 이미지와 VLM 이미지를 받은 뒤 `paddleocr-vl-build`로 CPU pipeline과 게이트웨이를 빌드하고 `paddleocr-vl-start`로 시작합니다. RAGFlow 설정에서는 일반 OCR `paddleocr-from-env`와 별도인 `paddleocr-vl-from-env`를 선택합니다. 두 인스턴스는 URL, Bearer 토큰과 알고리즘이 분리되어 자동 등록됩니다.
