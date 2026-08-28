# Runtime patch ownership

RAGFlow v0.26.4 원본은 수정하지 않습니다. 빌드가 고정된 upstream 파일의 SHA-256을 먼저 확인한 뒤 이 디렉터리의 작은 기능별 모듈이 한 번만 일치하는 anchor를 바꿉니다.

- `contract.py`: 해시와 anchor 개수 검증
- `dataset_settings.py`: 데이터셋·문서 파서 설정을 한 트랜잭션으로 전파

새 보강은 이 디렉터리에 기능별 모듈로 추가합니다. 기존 `apply-runtime-patches.py`의 검증된 패치는 동작을 바꾸는 대규모 이동을 피하고, 해당 기능을 수정할 때 모듈로 옮깁니다. 대상 upstream 버전이 달라지면 조용히 패치하지 않고 이미지 빌드를 실패시킵니다.
