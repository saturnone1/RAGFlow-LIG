from __future__ import annotations

import asyncio
import json
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
import pypdfium2 as pdfium
from PIL import Image
from quart import Quart, jsonify, request, send_file
from rapidocr import RapidOCR
from rapidocr.utils.typings import LangDet, LangRec, ModelType, OCRVersion


DEVICE = os.getenv("PADDLEOCR_DEVICE", "cpu").strip().lower()
if DEVICE not in {"cpu", "gpu"}:
    raise RuntimeError("PADDLEOCR_DEVICE must be cpu or gpu")

if DEVICE == "gpu":
    if "CUDAExecutionProvider" not in ort.get_available_providers():
        raise RuntimeError("CUDAExecutionProvider is unavailable")
    if not Path("/dev/nvidiactl").exists():
        raise RuntimeError("PADDLEOCR_DEVICE=gpu but no NVIDIA device is available")

OCR_PARAMS = {
    "Global.use_cls": False,
    "Global.log_level": os.getenv("PADDLEOCR_LOG_LEVEL", "info"),
    "Det.ocr_version": OCRVersion.PPOCRV5,
    "Det.lang_type": LangDet.CH,
    "Det.model_type": ModelType.MOBILE,
    "Rec.ocr_version": OCRVersion.PPOCRV5,
    "Rec.lang_type": LangRec.KOREAN,
    "Rec.model_type": ModelType.MOBILE,
    "EngineConfig.onnxruntime.use_cuda": DEVICE == "gpu",
}

OCR = RapidOCR(params=OCR_PARAMS)
RENDER_SCALE = float(os.getenv("PADDLEOCR_RENDER_SCALE", "2.0"))
if RENDER_SCALE <= 0:
    raise RuntimeError("PADDLEOCR_RENDER_SCALE must be positive")

JOB_TTL_SECONDS = int(os.getenv("PADDLEOCR_JOB_TTL_SECONDS", "3600"))
JOB_WORKERS = int(os.getenv("PADDLEOCR_JOB_WORKERS", "1"))
PROVISION_INTERVAL_SECONDS = int(os.getenv("PADDLEOCR_PROVISION_INTERVAL_SECONDS", "30"))
if JOB_WORKERS < 1:
    raise RuntimeError("PADDLEOCR_JOB_WORKERS must be positive")
if PROVISION_INTERVAL_SECONDS < 1:
    raise RuntimeError("PADDLEOCR_PROVISION_INTERVAL_SECONDS must be positive")

INTERNAL_TOKEN = os.getenv("PADDLEOCR_INTERNAL_TOKEN", "")
INTERNAL_BASE_URL = os.getenv("PADDLEOCR_INTERNAL_BASE_URL", "http://paddleocr:8080").rstrip("/")
JOB_DIRECTORY = Path(os.getenv("PADDLEOCR_JOB_DIRECTORY", "/tmp/lig-paddleocr-jobs"))
JOB_DIRECTORY.mkdir(parents=True, exist_ok=True)

app = Quart(__name__)
executor = ThreadPoolExecutor(max_workers=JOB_WORKERS, thread_name_prefix="paddleocr-ko")
jobs: dict[str, dict[str, Any]] = {}
jobs_lock = threading.Lock()
provisioner_stop = threading.Event()


def _render_ragflow_service_config() -> None:
    template_path = Path("/ragflow/conf/service_conf.yaml.template")
    config_path = Path("/ragflow/conf/service_conf.yaml")
    template = template_path.read_text(encoding="utf-8")

    def replace_default(match: re.Match[str]) -> str:
        name, default = match.group(1), match.group(2)
        return os.getenv(name) or default

    rendered = re.sub(r"\$\{([^}:]+):-([^}]*)\}", replace_default, template)
    rendered = re.sub(
        r"\$\{([^}]+)\}",
        lambda match: os.getenv(match.group(1), ""),
        rendered,
    )
    config_path.write_text(rendered, encoding="utf-8")


def _provision_ragflow_tenants() -> None:
    """Register the env-backed OCR model for existing and newly created tenants."""
    while not provisioner_stop.is_set():
        try:
            from api.db.db_models import Tenant
            from api.db.joint_services.tenant_model_service import ensure_paddleocr_from_env

            tenant_ids = [row.id for row in Tenant.select(Tenant.id).where(Tenant.status == "1")]
            for tenant_id in tenant_ids:
                for attempt in range(2):
                    try:
                        ensure_paddleocr_from_env(tenant_id)
                        break
                    except AttributeError:
                        # The first call can persist a new OCR instance before its
                        # object is available; retry to complete model provisioning.
                        if attempt:
                            raise
        except Exception:
            app.logger.exception("Failed to provision the Korean OCR model")
        _cleanup_jobs()
        provisioner_stop.wait(PROVISION_INTERVAL_SECONDS)


def _authorized() -> bool:
    if not INTERNAL_TOKEN:
        return True
    return request.headers.get("Authorization", "") == f"Bearer {INTERNAL_TOKEN}"


def _cleanup_jobs() -> None:
    cutoff = time.time() - JOB_TTL_SECONDS
    with jobs_lock:
        expired = [job_id for job_id, job in jobs.items() if job["updated_at"] < cutoff]
        expired_jobs = [jobs.pop(job_id) for job_id in expired]
    for job in expired_jobs:
        _remove_job_files(job)


def _remove_job_files(job: dict[str, Any]) -> None:
    for key in ("source_path", "result_path"):
        path = job.get(key)
        if not path:
            continue
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            app.logger.exception("Failed to remove OCR job file %s", path)


def _rectangular_box(points: Any) -> list[int]:
    coordinates = np.asarray(points, dtype=float)
    return [
        int(np.floor(coordinates[:, 0].min())),
        int(np.floor(coordinates[:, 1].min())),
        int(np.ceil(coordinates[:, 0].max())),
        int(np.ceil(coordinates[:, 1].max())),
    ]


def _ocr_image(image: Image.Image) -> dict[str, Any]:
    result = OCR(np.asarray(image.convert("RGB")), use_cls=False)
    texts = list(result.txts) if result.txts is not None else []
    boxes = [_rectangular_box(box) for box in result.boxes] if result.boxes is not None else []
    scores = [float(score) for score in result.scores] if result.scores is not None else []
    return {
        "prunedResult": {
            "rec_texts": texts,
            "rec_boxes": boxes,
            "rec_scores": scores,
        }
    }


def _write_page_result(output, page: dict[str, Any]) -> None:
    output.write(json.dumps({"result": {"ocrResults": [page]}}, ensure_ascii=False))
    output.write("\n")
    output.flush()


def _process_document(source_path: Path, result_path: Path) -> int:
    page_count = 0
    with source_path.open("rb") as source:
        is_pdf = source.read(4) == b"%PDF"

    with result_path.open("w", encoding="utf-8", newline="\n") as output:
        if is_pdf:
            document = pdfium.PdfDocument(str(source_path))
            try:
                for page in document:
                    image = page.render(scale=RENDER_SCALE).to_pil()
                    try:
                        _write_page_result(output, _ocr_image(image))
                        page_count += 1
                    finally:
                        image.close()
            finally:
                document.close()
        else:
            with Image.open(source_path) as image:
                _write_page_result(output, _ocr_image(image))
                page_count = 1
    return page_count


def _run_job(job_id: str, source_path: Path, result_path: Path) -> None:
    with jobs_lock:
        jobs[job_id].update(state="running", updated_at=time.time())
    try:
        page_count = _process_document(source_path, result_path)
        with jobs_lock:
            jobs[job_id].update(
                state="done",
                page_count=page_count,
                updated_at=time.time(),
            )
    except Exception as exc:
        app.logger.exception("Korean OCR job %s failed", job_id)
        result_path.unlink(missing_ok=True)
        with jobs_lock:
            jobs[job_id].update(state="failed", error=str(exc), updated_at=time.time())
    finally:
        source_path.unlink(missing_ok=True)


def _cleanup_job_files_at_startup() -> None:
    cutoff = time.time() - JOB_TTL_SECONDS
    for path in JOB_DIRECTORY.iterdir():
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            app.logger.exception("Failed to clean stale OCR job file %s", path)


@app.get("/health")
async def health():
    return jsonify(
        status="ok",
        device=DEVICE,
        provider="CUDAExecutionProvider" if DEVICE == "gpu" else "CPUExecutionProvider",
        model="korean_PP-OCRv5_mobile_rec",
    )


@app.post("/api/v2/ocr/jobs")
async def create_job():
    if not _authorized():
        return jsonify(error="unauthorized"), 401

    files = await request.files
    upload = files.get("file")
    if upload is None:
        return jsonify(error="file is required"), 400

    model = (await request.form).get("model", "PP-OCRv5")
    if model != "PP-OCRv5":
        return jsonify(error="this service supports PP-OCRv5 only"), 400

    _cleanup_jobs()
    job_id = uuid.uuid4().hex
    source_path = JOB_DIRECTORY / f"{job_id}.source"
    result_path = JOB_DIRECTORY / f"{job_id}.jsonl"
    await upload.save(source_path)
    if source_path.stat().st_size == 0:
        source_path.unlink(missing_ok=True)
        return jsonify(error="file is empty"), 400

    now = time.time()
    with jobs_lock:
        jobs[job_id] = {
            "state": "queued",
            "created_at": now,
            "updated_at": now,
            "result_token": uuid.uuid4().hex,
            "source_path": str(source_path),
            "result_path": str(result_path),
        }

    loop = asyncio.get_running_loop()
    loop.run_in_executor(executor, _run_job, job_id, source_path, result_path)
    return jsonify(data={"jobId": job_id})


@app.get("/api/v2/ocr/jobs/<job_id>")
async def get_job(job_id: str):
    if not _authorized():
        return jsonify(error="unauthorized"), 401

    _cleanup_jobs()
    with jobs_lock:
        job = dict(jobs.get(job_id, {}))
    if not job:
        return jsonify(error="job not found"), 404

    payload: dict[str, Any] = {"state": job["state"]}
    if job["state"] == "done":
        payload.update(
            resultJsonUrl=(
                f"{INTERNAL_BASE_URL}/api/v2/ocr/results/{job_id}.jsonl"
                f"?token={job['result_token']}"
            ),
            pageCount=job.get("page_count", 0),
        )
    elif job["state"] == "failed":
        payload["errorMsg"] = job.get("error", "OCR failed")
    return jsonify(data=payload)


@app.get("/api/v2/ocr/results/<job_id>.jsonl")
async def get_result(job_id: str):
    with jobs_lock:
        job = dict(jobs.get(job_id, {}))
    if not job:
        return jsonify(error="job not found"), 404
    if request.args.get("token", "") != job.get("result_token"):
        return jsonify(error="unauthorized"), 401
    if job.get("state") != "done":
        return jsonify(error="job is not complete"), 409
    result_path = Path(job["result_path"])
    if not result_path.is_file():
        return jsonify(error="result file is unavailable"), 410
    return await send_file(result_path, mimetype="application/x-ndjson")


if __name__ == "__main__":
    _render_ragflow_service_config()
    _cleanup_job_files_at_startup()
    threading.Thread(
        target=_provision_ragflow_tenants,
        name="paddleocr-tenant-provisioner",
        daemon=True,
    ).start()
    app.run(host="0.0.0.0", port=8080, use_reloader=False)
