ARG BASE_IMAGE=lig/ragflow-ui:v0.26.4-2
FROM ${BASE_IMAGE}

USER root

RUN uv pip install --python /ragflow/.venv/bin/python rapidocr==3.8.1

WORKDIR /opt/lig-paddleocr
COPY prefetch_models.py /opt/lig-paddleocr/prefetch_models.py
RUN /ragflow/.venv/bin/python /opt/lig-paddleocr/prefetch_models.py

COPY app.py /opt/lig-paddleocr/app.py

ENV PADDLEOCR_DEVICE=cpu \
    PADDLEOCR_INTERNAL_BASE_URL=http://paddleocr:8080 \
    PADDLEOCR_JOB_DIRECTORY=/tmp/lig-paddleocr-jobs \
    PADDLEOCR_RENDER_SCALE=2.0 \
    PADDLEOCR_JOB_WORKERS=1 \
    PADDLEOCR_JOB_TTL_SECONDS=3600 \
    PADDLEOCR_MAX_UPLOAD_BYTES=1073741824 \
    PADDLEOCR_MAX_PDF_PAGES=2000 \
    PADDLEOCR_MAX_PENDING_JOBS=8 \
    PADDLEOCR_MIN_FREE_BYTES=536870912 \
    PADDLEOCR_MAX_PAGE_PIXELS=50000000

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=10 \
  CMD curl --fail --silent http://127.0.0.1:8080/health || exit 1

ENTRYPOINT ["/ragflow/.venv/bin/python", "/opt/lig-paddleocr/app.py"]
