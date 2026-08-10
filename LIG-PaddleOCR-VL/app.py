from __future__ import annotations

import asyncio
import hmac
import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import requests
from quart import Quart, jsonify, request, send_file

from gateway_core import invoke_layout_parsing


MODEL_NAME = "PaddleOCR-VL-1.6"
UPSTREAM_URL = os.getenv("PADDLEOCR_VL_UPSTREAM_URL", "http://paddleocr-vl-api:8080").rstrip("/")
INTERNAL_BASE_URL = os.getenv("PADDLEOCR_VL_INTERNAL_BASE_URL", "http://paddleocr-vl:8080").rstrip("/")
INTERNAL_TOKEN = os.getenv("PADDLEOCR_INTERNAL_TOKEN", "")
JOB_DIRECTORY = Path(os.getenv("PADDLEOCR_VL_JOB_DIRECTORY", "/tmp/lig-paddleocr-vl-jobs"))
JOB_WORKERS = int(os.getenv("PADDLEOCR_VL_JOB_WORKERS", "1"))
JOB_TTL_SECONDS = int(os.getenv("PADDLEOCR_VL_JOB_TTL_SECONDS", "3600"))
MAX_UPLOAD_BYTES = int(os.getenv("PADDLEOCR_VL_MAX_UPLOAD_BYTES", "0"))
MAX_PENDING_JOBS = int(os.getenv("PADDLEOCR_VL_MAX_PENDING_JOBS", "8"))
REQUEST_TIMEOUT_SECONDS = float(os.getenv("PADDLEOCR_VL_REQUEST_TIMEOUT_SECONDS", "3600"))

if not INTERNAL_TOKEN:
    raise RuntimeError("PADDLEOCR_INTERNAL_TOKEN is required")
for name, value in (
    ("PADDLEOCR_VL_JOB_WORKERS", JOB_WORKERS),
    ("PADDLEOCR_VL_JOB_TTL_SECONDS", JOB_TTL_SECONDS),
    ("PADDLEOCR_VL_MAX_PENDING_JOBS", MAX_PENDING_JOBS),
):
    if value < 1:
        raise RuntimeError(f"{name} must be positive")
if MAX_UPLOAD_BYTES < 0:
    raise RuntimeError("PADDLEOCR_VL_MAX_UPLOAD_BYTES must be zero or positive")
if REQUEST_TIMEOUT_SECONDS <= 0:
    raise RuntimeError("PADDLEOCR_VL_REQUEST_TIMEOUT_SECONDS must be positive")

JOB_DIRECTORY.mkdir(parents=True, exist_ok=True)
app = Quart(__name__)
if MAX_UPLOAD_BYTES:
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES + 1024 * 1024
executor = ThreadPoolExecutor(max_workers=JOB_WORKERS, thread_name_prefix="paddleocr-vl")
jobs: dict[str, dict[str, Any]] = {}
jobs_lock = threading.Lock()


def _authorized() -> bool:
    return hmac.compare_digest(request.headers.get("Authorization", ""), f"Bearer {INTERNAL_TOKEN}")


def _cleanup_jobs() -> None:
    cutoff = time.time() - JOB_TTL_SECONDS
    with jobs_lock:
        expired = [
            job_id
            for job_id, job in jobs.items()
            if job["state"] in {"done", "failed", "canceled"} and job["updated_at"] < cutoff
        ]
        records = [jobs.pop(job_id) for job_id in expired]
    for record in records:
        for key in ("source_path", "result_path"):
            path = record.get(key)
            if path:
                Path(path).unlink(missing_ok=True)


def _run_job(job_id: str, source_path: Path, result_path: Path, optional_payload: dict[str, Any]) -> None:
    with jobs_lock:
        job = jobs.get(job_id)
        if not job or job["cancel_event"].is_set():
            return
        job.update(state="running", updated_at=time.time())
        cancel_event = job["cancel_event"]

    try:
        result = invoke_layout_parsing(
            source_path,
            optional_payload,
            UPSTREAM_URL,
            REQUEST_TIMEOUT_SECONDS,
        )
        if cancel_event.is_set():
            with jobs_lock:
                current = jobs.get(job_id)
                if current:
                    current.update(state="canceled", updated_at=time.time())
            return
        result_path.write_text(json.dumps({"result": result}, ensure_ascii=False) + "\n", encoding="utf-8")
        page_count = len(result.get("layoutParsingResults") or result.get("ocrResults") or [])
        with jobs_lock:
            current = jobs.get(job_id)
            if current:
                current.update(state="done", page_count=page_count, updated_at=time.time())
    except Exception as exc:
        app.logger.exception("PaddleOCR-VL job %s failed", job_id)
        with jobs_lock:
            current = jobs.get(job_id)
            if current and current["state"] != "canceled":
                current.update(state="failed", error=str(exc), updated_at=time.time())


@app.errorhandler(413)
async def request_too_large(_error):
    return jsonify(error=f"request exceeds the {MAX_UPLOAD_BYTES} byte upload limit"), 413


@app.get("/health")
async def health():
    upstream_ready = False
    try:
        upstream_response = await asyncio.to_thread(requests.get, f"{UPSTREAM_URL}/health", timeout=3)
        upstream_ready = upstream_response.ok
    except requests.RequestException:
        pass
    with jobs_lock:
        active = sum(job["state"] in {"uploading", "queued", "running"} for job in jobs.values())
    status = 200 if upstream_ready else 503
    return jsonify(status="ok" if upstream_ready else "waiting", model=MODEL_NAME, activeJobs=active), status


@app.post("/api/v2/ocr/jobs")
async def create_job():
    if not _authorized():
        return jsonify(error="unauthorized"), 401
    form = await request.form
    if form.get("model", MODEL_NAME) not in {"PaddleOCR-VL", MODEL_NAME}:
        return jsonify(error=f"this service supports {MODEL_NAME} only"), 400
    uploaded = (await request.files).get("file")
    if uploaded is None:
        return jsonify(error="file is required"), 400
    try:
        optional_payload = json.loads(form.get("optionalPayload", "{}"))
    except json.JSONDecodeError:
        return jsonify(error="optionalPayload must be valid JSON"), 400
    if not isinstance(optional_payload, dict):
        return jsonify(error="optionalPayload must be an object"), 400

    _cleanup_jobs()
    job_id = uuid.uuid4().hex
    source_path = JOB_DIRECTORY / f"{job_id}.pdf"
    result_path = JOB_DIRECTORY / f"{job_id}.jsonl"
    cancel_event = threading.Event()
    while True:
        with jobs_lock:
            active = sum(job["state"] in {"uploading", "queued", "running"} for job in jobs.values())
            if active < MAX_PENDING_JOBS:
                # Reserve a queue slot while the multipart body is copied to disk.
                jobs[job_id] = {
                    "state": "uploading",
                    "source_path": str(source_path),
                    "result_path": str(result_path),
                    "result_token": uuid.uuid4().hex,
                    "cancel_event": cancel_event,
                    "updated_at": time.time(),
                }
                break
        # Match the bundled PaddleOCR service: apply backpressure instead of
        # rejecting an otherwise valid document when the queue is busy.
        await asyncio.sleep(1)

    scheduled = False
    try:
        await uploaded.save(source_path)
        source_size = source_path.stat().st_size
        if source_size == 0:
            return jsonify(error="file is empty"), 400
        if MAX_UPLOAD_BYTES and source_size > MAX_UPLOAD_BYTES:
            return jsonify(error=f"request exceeds the {MAX_UPLOAD_BYTES} byte upload limit"), 413
        with jobs_lock:
            current = jobs.get(job_id)
            if not current:
                return jsonify(error="PaddleOCR-VL job reservation was lost"), 503
            if current["cancel_event"].is_set():
                return jsonify(error="PaddleOCR-VL job was canceled during upload"), 409
            current.update(state="queued", source_size=source_size, updated_at=time.time())
        future = executor.submit(_run_job, job_id, source_path, result_path, optional_payload)
        scheduled = True
        with jobs_lock:
            current = jobs.get(job_id)
            if current:
                current["future"] = future
        return jsonify(data={"jobId": job_id})
    except Exception:
        app.logger.exception("Failed to accept PaddleOCR-VL job %s", job_id)
        return jsonify(error="the PaddleOCR-VL upload could not be accepted"), 400
    finally:
        with jobs_lock:
            keep_job = scheduled and jobs.get(job_id) is not None
            if not keep_job:
                jobs.pop(job_id, None)
        if not keep_job:
            source_path.unlink(missing_ok=True)
            result_path.unlink(missing_ok=True)


@app.get("/api/v2/ocr/jobs/<job_id>")
async def get_job(job_id: str):
    if not _authorized():
        return jsonify(error="unauthorized"), 401
    _cleanup_jobs()
    with jobs_lock:
        job = dict(jobs.get(job_id, {}))
    if not job:
        return jsonify(error="job not found"), 404
    data: dict[str, Any] = {"state": job["state"]}
    if job["state"] == "done":
        data.update(
            resultJsonUrl=f"{INTERNAL_BASE_URL}/api/v2/ocr/results/{job_id}.jsonl?token={job['result_token']}",
            pageCount=job.get("page_count", 0),
        )
    elif job["state"] == "failed":
        data["errorMsg"] = job.get("error", "PaddleOCR-VL failed")
    return jsonify(data=data)


@app.delete("/api/v2/ocr/jobs/<job_id>")
async def cancel_job(job_id: str):
    if not _authorized():
        return jsonify(error="unauthorized"), 401
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return jsonify(error="job not found"), 404
        if job["state"] not in {"done", "failed", "canceled"}:
            job["cancel_event"].set()
            job.update(state="canceled", updated_at=time.time())
        state = job["state"]
    return jsonify(data={"jobId": job_id, "state": state})


@app.get("/api/v2/ocr/results/<job_id>.jsonl")
async def get_result(job_id: str):
    _cleanup_jobs()
    with jobs_lock:
        job = dict(jobs.get(job_id, {}))
    if not job:
        return jsonify(error="job not found"), 404
    if request.args.get("token", "") != job.get("result_token"):
        return jsonify(error="unauthorized"), 401
    if job["state"] != "done":
        return jsonify(error="job is not complete"), 409
    return await send_file(job["result_path"], mimetype="application/x-ndjson")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
