from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


UPSTREAM = os.environ.get("EMBEDDING_UPSTREAM_URL", "http://qwen3-embedding-tei:80").rstrip("/")
PORT = int(os.environ.get("EMBEDDING_ADAPTER_PORT", "8080"))
UPSTREAM_TIMEOUT_SECONDS = float(os.environ.get("EMBEDDING_UPSTREAM_TIMEOUT_SECONDS", "300"))
INSTRUCTION = os.environ.get(
    "EMBEDDING_QUERY_INSTRUCTION",
    "Given a user question, retrieve relevant passages from internal company documents that answer the question",
).strip()
MODEL = "Qwen/Qwen3-Embedding-0.6B"
state_lock = threading.Lock()
state = {
    "active_requests": 0,
    "completed_requests": 0,
    "failed_requests": 0,
    "client_disconnects": 0,
    "last_request_seconds": None,
    "last_error": None,
}


def prepare_embed_payload(payload: dict) -> dict:
    inputs = payload.get("inputs")
    if isinstance(inputs, str):
        return {**payload, "inputs": f"Instruct: {INSTRUCTION}\nQuery: {inputs}"}
    if isinstance(inputs, list) and all(isinstance(item, str) for item in inputs):
        return payload
    raise ValueError("inputs must be a string or an array of strings")


def _request_upstream(path: str, payload: bytes | None = None, method: str = "GET") -> tuple[int, bytes, str]:
    request = urllib.request.Request(
        f"{UPSTREAM}{path}",
        data=payload,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=UPSTREAM_TIMEOUT_SECONDS) as response:
            return response.status, response.read(), response.headers.get_content_type()
    except urllib.error.HTTPError as error:
        return error.code, error.read(), error.headers.get_content_type()


class Handler(BaseHTTPRequestHandler):
    server_version = "LIG-Qwen3-Embedding-Adapter/1"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}", flush=True)

    def _respond(self, status: int, body: bytes, content_type: str = "application/json") -> bool:
        try:
            self.send_response(status)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return True
        except (BrokenPipeError, ConnectionResetError):
            with state_lock:
                state["client_disconnects"] += 1
            return False

    def do_GET(self) -> None:
        if self.path == "/health":
            try:
                status, _, _ = _request_upstream("/health")
                if status != 200:
                    raise RuntimeError(f"TEI health returned HTTP {status}")
                body = json.dumps(
                    {
                        "status": "ok",
                        "model": MODEL,
                        "device": "cpu",
                        "query_instruction": True,
                        "requests": self._state_snapshot(),
                    }
                ).encode()
                self._respond(200, body)
            except Exception as error:
                body = json.dumps({"status": "error", "detail": str(error)}).encode()
                self._respond(503, body)
            return

        status, body, content_type = _request_upstream(self.path)
        self._respond(status, body, content_type)

    @staticmethod
    def _state_snapshot() -> dict:
        with state_lock:
            return dict(state)

    def do_POST(self) -> None:
        if self.path != "/embed":
            status, body, content_type = _request_upstream(
                self.path,
                self.rfile.read(int(self.headers.get("Content-Length", "0"))),
                "POST",
            )
            self._respond(status, body, content_type)
            return

        started_at = time.monotonic()
        with state_lock:
            state["active_requests"] += 1
        succeeded = False
        error_detail = None
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            payload = prepare_embed_payload(payload)
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            status, body, content_type = _request_upstream("/embed", encoded, "POST")
            succeeded = status < 400 and self._respond(status, body, content_type)
        except (ValueError, json.JSONDecodeError) as error:
            error_detail = str(error)
            self._respond(400, json.dumps({"error": str(error)}).encode())
        except Exception as error:
            error_detail = str(error)
            self._respond(502, json.dumps({"error": str(error)}).encode())
        finally:
            elapsed = round(time.monotonic() - started_at, 3)
            with state_lock:
                state["active_requests"] -= 1
                state["last_request_seconds"] = elapsed
                if succeeded:
                    state["completed_requests"] += 1
                    state["last_error"] = None
                else:
                    state["failed_requests"] += 1
                    state["last_error"] = error_detail or "upstream or client response failed"


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
