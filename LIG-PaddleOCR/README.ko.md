# LIG 한국어 PaddleOCR 서비스

복잡한 표·수식·차트·다국어 문서를 위한 선택형 `PaddleOCR-VL-1.6`은 `LIG-PaddleOCR-VL/`과 `LIG-Deployment`의 `paddleocr-vl-*` 관리 명령을 사용합니다. 기존 `paddleocr-from-env`와 새 `paddleocr-vl-from-env`는 RAGFlow에서 같은 방식으로 선택하며 서로 독립적으로 운영됩니다.

RAGFlow가 기대하는 `/api/v2/ocr/jobs` 계약을 제공하는 내부 OCR 서비스입니다.

- 인식: 공식 `korean_PP-OCRv5_mobile_rec` 계열 모델
- 검출: PP-OCRv5 mobile detection
- 런타임: RapidOCR 3.8.1 + ONNX Runtime
- 장치: CPU 이미지와 CUDA 12.8·cuDNN 9 GPU 이미지 분리
- 네트워크: Compose 내부에서만 RAGFlow가 호출하며 외부 포트는 localhost에만 게시

모델은 이미지 빌드 시 내려받아 포함되므로 실행 시 인터넷이 필요하지 않습니다. RAGFlow 원본 소스는 수정하지 않습니다.

업로드는 청크 단위로 임시 디스크에 저장하고 PDF는 페이지별로 OCR한 결과를 JSONL 파일에 즉시 기록합니다. 작업 원본과 결과는 TTL 이후 삭제되며 파일 크기나 페이지 수에 별도 상한을 두지 않습니다. 따라서 대형 문서를 처리할 때도 전체 PDF와 전체 OCR 결과를 Python 메모리에 동시에 보관하지 않습니다.

DeepDOC는 영어·중국어 문서의 레이아웃 및 표 처리 경로로 유지합니다. 한국어 스캔 PDF나 잘못된 글꼴 매핑 PDF에만 데이터셋 PDF 파서 `paddleocr-from-env`를 선택하십시오. LIG UI에서는 내부 API URL, 토큰과 `PP-OCRv5`가 자동 적용되므로 데이터셋 화면에서 별도로 입력하지 않습니다.
