FROM python:3.13-slim

RUN python -m pip install --no-cache-dir quart==0.20.0 requests==2.32.5

WORKDIR /opt/lig-paddleocr-vl
COPY app.py /opt/lig-paddleocr-vl/app.py
COPY gateway_core.py /opt/lig-paddleocr-vl/gateway_core.py

ENV PADDLEOCR_VL_UPSTREAM_URL=http://paddleocr-vl-api:8080 \
    PADDLEOCR_VL_INTERNAL_BASE_URL=http://paddleocr-vl:8080 \
    PADDLEOCR_VL_JOB_DIRECTORY=/tmp/lig-paddleocr-vl-jobs \
    PADDLEOCR_VL_JOB_WORKERS=1 \
    PADDLEOCR_VL_JOB_TTL_SECONDS=3600 \
    PADDLEOCR_VL_MAX_UPLOAD_BYTES=0 \
    PADDLEOCR_VL_MAX_PENDING_JOBS=8 \
    PADDLEOCR_VL_REQUEST_TIMEOUT_SECONDS=3600

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=10 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=4)" || exit 1

ENTRYPOINT ["python", "/opt/lig-paddleocr-vl/app.py"]
