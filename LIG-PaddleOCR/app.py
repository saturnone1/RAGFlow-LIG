from __future__ import annotations

import asyncio
import ctypes
import gc
import hmac
import json
import os
import re
import shutil
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

AVAILABLE_PROVIDERS = ort.get_available_providers()
if DEVICE == "gpu":
    from lig_runtime.gpu_detection import nvidia_device_ids

    gpu_ids = nvidia_device_ids()
    if "CUDAExecutionProvider" not in AVAILABLE_PROVIDERS or not gpu_ids:
        raise RuntimeError(
            "PADDLEOCR_DEVICE=gpu requires CUDAExecutionProvider and an NVIDIA "
            f"device; providers={AVAILABLE_PROVIDERS}, gpuIds={gpu_ids}"
        )

MODEL_DIRECTORY = Path(__import__("rapidocr").__file__).resolve().parent / "models"
DETECTION_MODEL_PATH = MODEL_DIRECTORY / "ch_PP-OCRv5_det_mobile.onnx"
RECOGNITION_MODEL_PATH = MODEL_DIRECTORY / "korean_PP-OCRv5_rec_mobile.onnx"
for model_path in (DETECTION_MODEL_PATH, RECOGNITION_MODEL_PATH):
    if not model_path.is_file():
        raise RuntimeError(f"required PaddleOCR model is missing: {model_path}")

recognition_metadata = ort.InferenceSession(
    str(RECOGNITION_MODEL_PATH), providers=["CPUExecutionProvider"]
).get_modelmeta().custom_metadata_map
recognition_characters = recognition_metadata.get("character", "")
if not any("가" <= character <= "힣" for character in recognition_characters):
    raise RuntimeError("the configured PaddleOCR recognition model has no Korean character metadata")

OCR_PARAMS = {
    "Global.use_cls": False,
    "Global.log_level": os.getenv("PADDLEOCR_LOG_LEVEL", "info"),
    "Det.ocr_version": OCRVersion.PPOCRV5,
    "Det.lang_type": LangDet.CH,
    "Det.model_type": ModelType.MOBILE,
    "Det.model_path": str(DETECTION_MODEL_PATH),
    "Rec.ocr_version": OCRVersion.PPOCRV5,
    "Rec.lang_type": LangRec.KOREAN,
    "Rec.model_type": ModelType.MOBILE,
    "Rec.model_path": str(RECOGNITION_MODEL_PATH),
    "EngineConfig.onnxruntime.use_cuda": DEVICE == "gpu",
}

OCR = RapidOCR(params=OCR_PARAMS)
OCR_SESSION_PROVIDERS = {
    name: component.session.session.get_providers()
    for name, component in (("detector", OCR.text_det), ("recognizer", OCR.text_rec))
}
required_provider = "CUDAExecutionProvider" if DEVICE == "gpu" else "CPUExecutionProvider"
invalid_sessions = {
    name: providers
    for name, providers in OCR_SESSION_PROVIDERS.items()
    if not providers or providers[0] != required_provider
}
if invalid_sessions:
    raise RuntimeError(f"PaddleOCR must use {required_provider}: {invalid_sessions}")
DEFAULT_RENDER_DPI = int(os.getenv("PADDLEOCR_RENDER_DPI", "144"))
if DEFAULT_RENDER_DPI < 1:
    raise RuntimeError("PADDLEOCR_RENDER_DPI must be a positive integer")

JOB_TTL_SECONDS = int(os.getenv("PADDLEOCR_JOB_TTL_SECONDS", "3600"))
JOB_WORKERS = int(os.getenv("PADDLEOCR_JOB_WORKERS", "1"))
MAX_UPLOAD_BYTES = int(os.getenv("PADDLEOCR_MAX_UPLOAD_BYTES", "0"))
MAX_PDF_PAGES = int(os.getenv("PADDLEOCR_MAX_PDF_PAGES", "0"))
MAX_PENDING_JOBS = int(os.getenv("PADDLEOCR_MAX_PENDING_JOBS", "8"))
MIN_FREE_BYTES = int(os.getenv("PADDLEOCR_MIN_FREE_BYTES", str(512 * 1024 * 1024)))
MAX_PAGE_PIXELS = int(os.getenv("PADDLEOCR_MAX_PAGE_PIXELS", "50000000"))
OCR_BYTES_PER_PIXEL = int(os.getenv("PADDLEOCR_ESTIMATED_BYTES_PER_PIXEL", "48"))
MEMORY_POLL_SECONDS = float(os.getenv("PADDLEOCR_MEMORY_POLL_SECONDS", "2"))
PROVISION_INTERVAL_SECONDS = int(os.getenv("PADDLEOCR_PROVISION_INTERVAL_SECONDS", "30"))
for setting_name, setting_value in (
    ("PADDLEOCR_JOB_TTL_SECONDS", JOB_TTL_SECONDS),
    ("PADDLEOCR_JOB_WORKERS", JOB_WORKERS),
    ("PADDLEOCR_MAX_PENDING_JOBS", MAX_PENDING_JOBS),
    ("PADDLEOCR_MIN_FREE_BYTES", MIN_FREE_BYTES),
    ("PADDLEOCR_MAX_PAGE_PIXELS", MAX_PAGE_PIXELS),
    ("PADDLEOCR_ESTIMATED_BYTES_PER_PIXEL", OCR_BYTES_PER_PIXEL),
    ("PADDLEOCR_PROVISION_INTERVAL_SECONDS", PROVISION_INTERVAL_SECONDS),
):
    if setting_value < 1:
        raise RuntimeError(f"{setting_name} must be positive")
if MAX_PDF_PAGES < 0:
    raise RuntimeError("PADDLEOCR_MAX_PDF_PAGES must be zero (unlimited) or positive")
if MAX_UPLOAD_BYTES < 0:
    raise RuntimeError("PADDLEOCR_MAX_UPLOAD_BYTES must be zero (unlimited) or positive")
if MEMORY_POLL_SECONDS <= 0:
    raise RuntimeError("PADDLEOCR_MEMORY_POLL_SECONDS must be positive")

INTERNAL_TOKEN = os.getenv("PADDLEOCR_INTERNAL_TOKEN", "")
if not INTERNAL_TOKEN:
    raise RuntimeError("PADDLEOCR_INTERNAL_TOKEN is required")
INTERNAL_BASE_URL = os.getenv("PADDLEOCR_INTERNAL_BASE_URL", "http://paddleocr:8080").rstrip("/")
JOB_DIRECTORY = Path(os.getenv("PADDLEOCR_JOB_DIRECTORY", "/tmp/lig-paddleocr-jobs"))
JOB_DIRECTORY.mkdir(parents=True, exist_ok=True)

app = Quart(__name__)
if MAX_UPLOAD_BYTES:
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES + 1024 * 1024
executor = ThreadPoolExecutor(max_workers=JOB_WORKERS, thread_name_prefix="paddleocr-ko")
jobs: dict[str, dict[str, Any]] = {}
jobs_lock = threading.Lock()
try:
    _malloc_trim = ctypes.CDLL("libc.so.6").malloc_trim
except (OSError, AttributeError):
    _malloc_trim = None
provisioner_stop = threading.Event()


class OcrResourceLimitError(ValueError):
    pass


class OcrJobCanceled(Exception):
    pass


@app.errorhandler(413)
async def request_too_large(_error):
    return jsonify(error=f"request exceeds the {MAX_UPLOAD_BYTES} byte OCR upload limit"), 413


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
    """Register environment-backed OCR models for existing and new tenants."""
    while not provisioner_stop.is_set():
        try:
            from api.db.db_models import Tenant
            from api.db.joint_services.tenant_model_service import (
                ensure_paddleocr_from_env,
                ensure_paddleocr_vl_from_env,
            )

            tenant_ids = [
                row.id
                for row in Tenant.select(Tenant.id)
                .where(Tenant.status == "1")
                .order_by(Tenant.create_time, Tenant.id)
            ]
            for tenant_id in tenant_ids:
                for attempt in range(2):
                    try:
                        ensure_paddleocr_from_env(tenant_id)
                        ensure_paddleocr_vl_from_env(tenant_id)
                        break
                    except AttributeError:
                        # The first call can persist a new OCR instance before its
                        # object is available; retry to complete model provisioning.
                        if attempt:
                            raise
        except Exception:
            app.logger.exception("Failed to provision environment-backed OCR models")
        _cleanup_jobs()
        provisioner_stop.wait(PROVISION_INTERVAL_SECONDS)


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


def _host_available_memory() -> int:
    candidates: list[int] = []
    try:
        values = {}
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            name, value = line.split(":", 1)
            values[name] = int(value.strip().split()[0]) * 1024
        if values.get("MemAvailable", 0) > 0:
            candidates.append(values["MemAvailable"])
    except (OSError, ValueError, KeyError):
        pass

    try:
        limit_text = Path("/sys/fs/cgroup/memory.max").read_text(encoding="ascii").strip()
        if limit_text != "max":
            limit = int(limit_text)
            current = int(Path("/sys/fs/cgroup/memory.current").read_text(encoding="ascii").strip())
            candidates.append(max(0, limit - current))
    except (OSError, ValueError):
        pass

    try:
        limit = int(Path("/sys/fs/cgroup/memory/memory.limit_in_bytes").read_text(encoding="ascii").strip())
        current = int(Path("/sys/fs/cgroup/memory/memory.usage_in_bytes").read_text(encoding="ascii").strip())
        if 0 < limit < 2**60:
            candidates.append(max(0, limit - current))
    except (OSError, ValueError):
        pass

    return min(candidates) if candidates else 2**63 - 1


def _release_page_memory() -> None:
    gc.collect()
    if _malloc_trim is not None:
        _malloc_trim(0)


def _raise_if_canceled(cancel_event: threading.Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise OcrJobCanceled("OCR job canceled")


def _wait_for_memory(cancel_event: threading.Event | None = None) -> int:
    while True:
        _raise_if_canceled(cancel_event)
        available = _host_available_memory()
        if available > MIN_FREE_BYTES:
            return available
        _release_page_memory()
        time.sleep(MEMORY_POLL_SECONDS)


def _page_pixel_budget(available_memory: int | None = None) -> int:
    available = _host_available_memory() if available_memory is None else available_memory
    usable = max(1, available - MIN_FREE_BYTES)
    adaptive_budget = max(1, usable // max(1, OCR_BYTES_PER_PIXEL * JOB_WORKERS))
    return max(1, min(MAX_PAGE_PIXELS, adaptive_budget))


def _pdf_render_scale(
    width: float,
    height: float,
    render_dpi: int,
    available_memory: int | None = None,
) -> float:
    if width <= 0 or height <= 0:
        raise OcrResourceLimitError("PDF page dimensions must be positive")
    if render_dpi < 1:
        raise OcrResourceLimitError("PDF render DPI must be a positive integer")
    requested_scale = render_dpi / 72.0
    return min(requested_scale, (_page_pixel_budget(available_memory) / (width * height)) ** 0.5)


def _fit_image_to_memory(image: Image.Image, available_memory: int) -> Image.Image:
    if image.width <= 0 or image.height <= 0:
        raise OcrResourceLimitError("image dimensions must be positive")
    budget = _page_pixel_budget(available_memory)
    if image.width * image.height <= budget:
        return image.convert("RGB")
    scale = (budget / (image.width * image.height)) ** 0.5
    size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
    return image.convert("RGB").resize(size, Image.Resampling.LANCZOS)


def _ocr_image(image: Image.Image, available_memory: int) -> dict[str, Any]:
    rgb_image = _fit_image_to_memory(image, available_memory)
    try:
        result = OCR(np.asarray(rgb_image), use_cls=False)
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
    finally:
        rgb_image.close()


def _write_page_result(output, page: dict[str, Any]) -> None:
    output.write(json.dumps({"result": {"ocrResults": [page]}}, ensure_ascii=False))
    output.write("\n")
    output.flush()


def _process_document(
    source_path: Path,
    result_path: Path,
    render_dpi: int = DEFAULT_RENDER_DPI,
    progress=None,
    cancel_event: threading.Event | None = None,
) -> int:
    page_count = 0
    with source_path.open("rb") as source:
        is_pdf = source.read(4) == b"%PDF"

    with result_path.open("w", encoding="utf-8", newline="\n") as output:
        if is_pdf:
            document = pdfium.PdfDocument(str(source_path))
            try:
                for page in document:
                    try:
                        _raise_if_canceled(cancel_event)
                        available = _wait_for_memory(cancel_event)
                        width, height = page.get_size()
                        image = page.render(scale=_pdf_render_scale(width, height, render_dpi, available)).to_pil()
                        try:
                            _raise_if_canceled(cancel_event)
                            _write_page_result(output, _ocr_image(image, available))
                            _raise_if_canceled(cancel_event)
                            page_count += 1
                            if progress:
                                progress(page_count)
                        finally:
                            image.close()
                    finally:
                        page.close()
                        _release_page_memory()
            finally:
                document.close()
        else:
            with Image.open(source_path) as image:
                available = _wait_for_memory(cancel_event)
                _raise_if_canceled(cancel_event)
                _write_page_result(output, _ocr_image(image, available))
                _raise_if_canceled(cancel_event)
                page_count = 1
                if progress:
                    progress(page_count)
            _release_page_memory()
    return page_count


def _run_job(job_id: str, source_path: Path, result_path: Path, render_dpi: int) -> None:
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            source_path.unlink(missing_ok=True)
            return
        cancel_event = job["cancel_event"]
        if cancel_event.is_set():
            job.update(state="canceled", updated_at=time.time())
            source_path.unlink(missing_ok=True)
            return
        job.update(state="running", updated_at=time.time())

    def update_progress(page_count: int) -> None:
        _raise_if_canceled(cancel_event)
        with jobs_lock:
            job = jobs.get(job_id)
            if job is not None:
                job.update(processed_pages=page_count, updated_at=time.time())

    try:
        page_count = _process_document(source_path, result_path, render_dpi, update_progress, cancel_event)
        with jobs_lock:
            job = jobs.get(job_id)
            if job is not None:
                job.update(
                    state="done",
                    page_count=page_count,
                    processed_pages=page_count,
                    updated_at=time.time(),
                )
    except OcrJobCanceled:
        result_path.unlink(missing_ok=True)
        with jobs_lock:
            job = jobs.get(job_id)
            if job is not None:
                job.update(state="canceled", updated_at=time.time())
    except Exception as exc:
        app.logger.exception("Korean OCR job %s failed", job_id)
        result_path.unlink(missing_ok=True)
        with jobs_lock:
            job = jobs.get(job_id)
            if job is not None:
                job.update(state="failed", error=str(exc), updated_at=time.time())
    finally:
        source_path.unlink(missing_ok=True)


def _cleanup_job_files_at_startup() -> None:
    for path in JOB_DIRECTORY.iterdir():
        try:
            # The in-memory job registry is empty after a process restart, so
            # every pre-existing file is orphaned and safe to remove.
            if path.is_file():
                path.unlink()
        except OSError:
            app.logger.exception("Failed to clean stale OCR job file %s", path)


@app.get("/health")
async def health():
    with jobs_lock:
        active_jobs = sum(job["state"] in {"uploading", "queued", "running"} for job in jobs.values())
    return jsonify(
        status="ok",
        device=DEVICE,
        provider=OCR_SESSION_PROVIDERS,
        model="korean_PP-OCRv5_mobile_rec",
        activeJobs=active_jobs,
        maxPendingJobs=MAX_PENDING_JOBS,
        defaultRenderDpi=DEFAULT_RENDER_DPI,
    )


@app.post("/api/v2/ocr/jobs")
async def create_job():
    if not _authorized():
        return jsonify(error="unauthorized"), 401

    files = await request.files
    upload = files.get("file")
    if upload is None:
        return jsonify(error="file is required"), 400

    form = await request.form
    model = form.get("model", "PP-OCRv5")
    if model != "PP-OCRv5":
        return jsonify(error="this service supports PP-OCRv5 only"), 400
    try:
        render_dpi = int(form.get("renderDpi", str(DEFAULT_RENDER_DPI)))
        if render_dpi < 1:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify(error="renderDpi must be a positive integer"), 400

    _cleanup_jobs()
    job_id = uuid.uuid4().hex
    source_path = JOB_DIRECTORY / f"{job_id}.source"
    result_path = JOB_DIRECTORY / f"{job_id}.jsonl"
    now = time.time()
    while True:
        with jobs_lock:
            active_jobs = sum(job["state"] in {"uploading", "queued", "running"} for job in jobs.values())
            if active_jobs < MAX_PENDING_JOBS:
                jobs[job_id] = {
                    "state": "uploading",
                    "created_at": now,
                    "updated_at": now,
                    "result_token": uuid.uuid4().hex,
                    "source_path": str(source_path),
                    "result_path": str(result_path),
                    "cancel_event": threading.Event(),
                    "render_dpi": render_dpi,
                }
                break
        await asyncio.sleep(MEMORY_POLL_SECONDS)

    scheduled = False
    try:
        expected_bytes = request.content_length or 0
        if MAX_UPLOAD_BYTES:
            expected_bytes = min(expected_bytes or MAX_UPLOAD_BYTES, MAX_UPLOAD_BYTES)
        while shutil.disk_usage(JOB_DIRECTORY).free < expected_bytes + MIN_FREE_BYTES:
            await asyncio.sleep(MEMORY_POLL_SECONDS)
        await upload.save(source_path)
        source_size = source_path.stat().st_size
        if source_size == 0:
            return jsonify(error="file is empty"), 400
        if MAX_UPLOAD_BYTES and source_size > MAX_UPLOAD_BYTES:
            return jsonify(error=f"file exceeds the {MAX_UPLOAD_BYTES} byte OCR limit"), 413

        with source_path.open("rb") as source:
            is_pdf = source.read(4) == b"%PDF"
        if is_pdf:
            document = pdfium.PdfDocument(str(source_path))
            try:
                page_count = len(document)
                if MAX_PDF_PAGES and page_count > MAX_PDF_PAGES:
                    return jsonify(error=f"PDF exceeds the {MAX_PDF_PAGES} page OCR limit"), 413
            finally:
                document.close()
        else:
            with Image.open(source_path) as image:
                if image.width <= 0 or image.height <= 0:
                    return jsonify(error="image dimensions must be positive"), 400

        with jobs_lock:
            job = jobs.get(job_id)
            if job is None:
                return jsonify(error="OCR job reservation was lost"), 503
            job.update(state="queued", source_size=source_size, updated_at=time.time())

        future = executor.submit(_run_job, job_id, source_path, result_path, render_dpi)
        scheduled = True
        with jobs_lock:
            job = jobs.get(job_id)
            if job is not None:
                job["future"] = future
        return jsonify(data={"jobId": job_id})
    except OcrResourceLimitError as exc:
        return jsonify(error=str(exc)), 413
    except Exception:
        app.logger.exception("Failed to accept Korean OCR job %s", job_id)
        return jsonify(error="the OCR upload could not be accepted"), 400
    finally:
        with jobs_lock:
            reserved = jobs.get(job_id)
            keep_job = scheduled and reserved is not None
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

    payload: dict[str, Any] = {
        "state": job["state"],
        "renderDpi": job.get("render_dpi", DEFAULT_RENDER_DPI),
    }
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


@app.delete("/api/v2/ocr/jobs/<job_id>")
async def cancel_job(job_id: str):
    if not _authorized():
        return jsonify(error="unauthorized"), 401

    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            return jsonify(error="job not found"), 404
        if job["state"] in {"done", "failed", "canceled"}:
            return jsonify(data={"jobId": job_id, "state": job["state"]})
        job["cancel_event"].set()
        future = job.get("future")
        canceled_before_start = bool(future and future.cancel())
        job.update(
            state="canceled" if canceled_before_start else "canceling",
            updated_at=time.time(),
        )
        payload = {"jobId": job_id, "state": job["state"]}

    if canceled_before_start:
        _remove_job_files(job)
    return jsonify(data=payload), 202


@app.get("/api/v2/ocr/results/<job_id>.jsonl")
async def get_result(job_id: str):
    _cleanup_jobs()
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
