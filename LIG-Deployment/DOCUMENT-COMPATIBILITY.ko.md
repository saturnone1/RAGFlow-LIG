# 문서 호환성 및 암호 키 운영

이 문서는 LIG RAGFlow v0.26.4 오버레이의 실제 업로드·청킹 계약을 설명합니다. 업로드 API는 파일을 저장하기 전에 확장자와 청킹 방식의 조합을 검사하며, 실패 응답과 웹 화면에 사용할 수 있는 방식 또는 변환 형식을 함께 표시합니다. 확장자만 허용된다고 청킹 품질까지 보장되는 것은 아니므로 실제 문서 표본으로 결과를 검수해야 합니다.

아래 표는 내장 청킹 방식의 계약입니다. 사용자 정의 ingestion pipeline은 자체 파일 단계의 suffix 계약을 사용하므로 이 표로 선제 차단하지 않습니다.

## 청킹 방식별 확장자

| 청킹 방식 | 직접 처리하는 확장자 |
| --- | --- |
| `naive`, `knowledge_graph` | `doc`, `docx`, `pdf`, `csv`, `xls`, `xlsx`, `html`, `htm`, `epub`, `json`, `jsonl`, `ldjson`, `txt`, `md`, `markdown`, `mdx`, `py`, `js`, `java`, `c`, `cpp`, `h`, `php`, `go`, `ts`, `sh`, `cs`, `kt`, `sql` |
| `book` | `doc`, `docx`, `pdf`, `txt`, `htm`, `html` |
| `laws` | `doc`, `docx`, `pdf`, `txt`, `md`, `markdown`, `mdx`, `htm`, `html` |
| `manual` | `doc`, `docx`, `pdf` |
| `paper` | `pdf` |
| `presentation` | `ppt`, `pptx`, `pdf` |
| `table` | `xls`, `xlsx`, `txt`, `csv` |
| `qa` | `xls`, `xlsx`, `txt`, `csv`, `pdf`, `md`, `markdown`, `mdx`, `docx` |
| `one` | `doc`, `docx`, `pdf`, `xls`, `xlsx`, `txt`, `md`, `markdown`, `mdx`, `htm`, `html` |
| `resume` | `pdf`, `docx`, `txt` |
| `tag` | `xls`, `xlsx`, `txt`, `csv` |
| `email` | `eml` |
| `picture` | `jpg`, `jpeg`, `png`, `tif`, `gif`, `webp`, `avif`, `apng`, `ico`, `icon`, `pcx`, `tga`, `psd`, `mp4`, `mov`, `avi`, `flv`, `mpeg`, `mpg`, `webm`, `wmv`, `3gp`, `3gpp`, `mkv` |
| `audio` | `da`, `wave`, `wav`, `mp3`, `aac`, `flac`, `ogg`, `aiff`, `au`, `midi`, `wma`, `realaudio`, `vqf`, `oggvorbis`, `ape` |

일반 HWP 5와 HWPX는 UTF-8 텍스트로 변환한 뒤 처리하므로 `txt`를 받는 방식에서 사용할 수 있습니다. 기본 권장은 `naive`입니다. PPT/PPTX, 이미지·영상, 음성, EML은 업로드 시 각각 `presentation`, `picture`, `audio`, `email` 방식으로 자동 선택됩니다.

현재 업로드 형식 목록에 있더라도 실제 파서가 없는 `msg`, `rtf`, `wps`, `pages`, `numbers`, `key`, `yml`, `yaml`, `xml`, `ini`, `hlp` 등은 사전검증에서 거부하고 EML, DOCX, PDF, XLSX, CSV, PPTX, TXT 또는 Markdown 변환을 안내합니다. 파일 확장자를 바꾸는 것만으로는 변환되지 않습니다.

## 파일 열기 암호와 제외 범위

파일 열기 암호는 PDF, DOC/DOCX, XLS/XLSX, PPT/PPTX, HWP/HWPX 입력란에 선택적으로 받을 수 있습니다. 최신 Office OOXML과 HWPX는 업로드 때 암호를 검증합니다. 원본 암호화 파일은 그대로 저장하며, 암호는 AES-256-GCM으로 봉인해 문서 설정에 저장합니다. 일반 문서에 암호를 잘못 입력했거나 암호 문서를 일반 문서로 교체한 경우에는 제출·잔존 암호 상태를 저장 전에 제거하므로 일반 문서가 암호 필요 상태로 바뀌지 않습니다. 평문 Office/PDF는 복호화 캐시에 넣지 않고, 변환이 필요한 HWP/HWPX 또는 암호 문서만 프로세스별 128 MiB·항목별 64 MiB·10분 TTL 캐시와 동일 문서 단일실행 제어를 사용합니다.

다음 항목은 지원하지 않습니다.

- 암호화된 바이너리 HWP: 검증된 공개 복호화 경로가 없으므로 HWPX 또는 DOCX로 다시 저장
- HWP 배포용 문서와 Office 편집·시트 보호: 파일 열기 암호가 아닌 사용 권한 제한
- 소유자 암호가 없는 PDF 권한 제한: 제한을 우회하지 않으며, 올바른 소유자(권한) 암호를 입력한 경우에만 처리
- Microsoft IRM/MIP/AIP, FASOO DRM 등 계정·인증서·권한 서버 기반 보호
- 사용 중인 공개 라이브러리가 해석하지 못하는 오래된 DOC/XLS/PPT 암호 규격

HWP/HWPX 변환은 문단, 표, 각주·미주·머리말·꼬리말 텍스트와 포함 객체의 경로 목록을 보존합니다. 글꼴·정밀 배치·도형·수식의 시각적 의미, 변경 추적, 매크로, 포함 파일 본문과 이미지 OCR은 보존하지 않습니다. 이러한 요소가 검색 근거라면 PDF로 내보내거나 별도 OCR/VLM 경로를 사용하십시오.

악성 또는 손상 문서의 자원 고갈을 줄이기 위해 HWPX ZIP 항목 수·개별/전체 확장 크기·XML 크기/요소 수·암호화 항목 수·PBKDF 반복량·경로 중복을 제한하고, HWP 입력 크기·OLE 스트림 수·본문 섹션 수·레코드 수·확장 본문 크기를 제한합니다. 현재 상한은 운영 안전장치이며 정상 문서가 거부되면 임의로 해제하지 말고 문서 구조와 실제 메모리 사용량을 먼저 확인하십시오.

## 암호 키 감사와 회전

`.env.secret`의 다음 세 값을 모든 RAGFlow API/작업자 노드에 동일하게 배포합니다.

```dotenv
LIG_DOCUMENT_PASSWORD_KEY=<base64 32-byte active key>
LIG_DOCUMENT_PASSWORD_KEY_ID=primary
LIG_DOCUMENT_PASSWORD_PREVIOUS_KEYS=
```

키 값은 Git, 진단 파일, 에어갭 이미지/번들에 넣지 말고 별도 암호화 백업에 보관합니다. 노드별 설정 일치 여부는 실제 키를 출력하지 않는 지문으로 확인합니다.

```powershell
.\rotate-document-password-key.ps1 audit
.\rotate-document-password-key.ps1 audit -ExpectedFingerprint <다른 노드에서 확인한 지문>
```

단일 Compose 배포에서 회전하려면 다음을 실행합니다. 스크립트는 새 32바이트 키와 키 ID를 만들고, 기존 키를 이전 키 목록에 보존하고, 서비스를 재시작한 다음 DB의 저장 토큰을 배치 재봉인합니다. 새 설정으로 서비스를 시작하지 못하면 `.env.secret` 백업을 복원합니다. 재봉인 도중 실패하면 일부 배치가 이미 새 키를 참조할 수 있으므로 새 활성 키와 이전 키를 모두 유지하며, 원인을 해결한 뒤 `audit`과 재봉인을 다시 실행합니다.

```powershell
.\rotate-document-password-key.ps1 rotate
# 변경관리용 고정 ID가 필요할 때
.\rotate-document-password-key.ps1 rotate -NewKeyId key-2026-q3
```

다중 서버에서는 문서 업로드·커넥터 동기화·문서 설정 변경을 잠시 중지하고, 모든 노드에 새 활성 키와 이전 키를 먼저 배포하고 모든 노드의 지문이 같은지 확인한 뒤 한 노드에서 재봉인을 실행해야 합니다. 재봉인은 전체 설정을 메모리에 쌓지 않고 DB를 순회하며 최대 100건씩 행 잠금 트랜잭션으로 처리합니다. 재봉인 감사 결과가 0이고 모든 노드가 같은 지문으로 정상 처리되는 것을 확인하기 전에는 이전 키를 제거하지 마십시오. 이전 키는 최대 15개입니다.

복구할 때는 서비스와 DB 쓰기를 중지하고 Docker 데이터/DB 백업과 같은 시점의 `.env.secret`을 함께 복원합니다. 키 회전 직전 자동 백업은 `LIG-Deployment\.env.secret.<UTC 시각>.bak`이며 Git에서 제외됩니다. DB만 이전 시점으로 복구하거나 `.env.secret`만 되돌리면 일부 문서 토큰의 키 ID가 맞지 않을 수 있으므로, 현재 키와 필요한 이전 키를 모두 넣은 뒤 `audit`이 0이 될 때까지 재봉인하십시오.
