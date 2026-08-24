"""Shell-free RAGFlow container supervisor for the LIG deployment."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path("/ragflow")
PYTHON = str(ROOT / ".venv/bin/python")
STOP = threading.Event()
CHILDREN: list[subprocess.Popen] = []


def render_configuration() -> None:
    template = (ROOT / "conf/service_conf.yaml.template").read_text(encoding="utf-8")

    def default_value(match: re.Match[str]) -> str:
        return os.environ.get(match.group(1)) or match.group(2)

    rendered = re.sub(r"\$\{([^}:]+):-([^}]*)}", default_value, template)
    rendered = re.sub(r"\$\{([^}]+)}", lambda match: os.environ.get(match.group(1), ""), rendered)
    (ROOT / "conf/service_conf.yaml").write_text(rendered, encoding="utf-8")


def configure_nginx() -> None:
    scheme = os.environ.get("API_PROXY_SCHEME", "python").lower()
    source_name = {"hybrid": "ragflow.conf.hybrid", "go": "ragflow.conf.golang"}.get(scheme, "ragflow.conf.python")
    shutil.copyfile(Path("/etc/nginx/conf.d") / source_name, "/etc/nginx/conf.d/ragflow.conf")


def ensure_docling() -> None:
    if os.environ.get("USE_DOCLING", "false").lower() != "true" or importlib.util.find_spec("docling"):
        return
    version = os.environ.get("DOCLING_VERSION", "==2.71.0")
    subprocess.run(
        [
            "uv", "pip", "install", "--python", PYTHON,
            "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
            "--extra-index-url", "https://pypi.org/simple", "--no-cache-dir", f"docling{version}",
        ],
        check=True,
    )


def initialize_database() -> None:
    from api.db.db_models import init_database_tables

    init_database_tables()


def spawn(command: list[str], *, environment: dict[str, str] | None = None) -> subprocess.Popen:
    process = subprocess.Popen(command, cwd=ROOT, env=environment)
    CHILDREN.append(process)
    return process


def restart_forever(command: list[str], *, environment: dict[str, str] | None = None) -> None:
    while not STOP.is_set():
        process = spawn(command, environment=environment)
        while process.poll() is None and not STOP.wait(1):
            pass
        if STOP.is_set():
            return
        time.sleep(1)


def start_loop(command: list[str], *, environment: dict[str, str] | None = None) -> None:
    threading.Thread(target=restart_forever, args=(command,), kwargs={"environment": environment}, daemon=True).start()


def worker_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for candidate in (Path("/usr/lib/x86_64-linux-gnu/libjemalloc.so.2"), Path("/usr/lib64/libjemalloc.so.2")):
        if candidate.is_file():
            environment["LD_PRELOAD"] = str(candidate)
            break
    return environment


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--disable-webserver", action="store_true")
    parser.add_argument("--disable-taskexecutor", action="store_true")
    parser.add_argument("--disable-datasync", action="store_true")
    parser.add_argument("--enable-mcpserver", action="store_true")
    parser.add_argument("--enable-adminserver", action="store_true")
    parser.add_argument("--init-model-provider-tables", action="store_true")
    parser.add_argument("--init-superuser", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--consumer-no-beg", type=int, default=0)
    parser.add_argument("--consumer-no-end", type=int, default=0)
    parser.add_argument("--host-id")
    parser.add_argument("--mcp-host", default="127.0.0.1")
    parser.add_argument("--mcp-port", type=int, default=9382)
    parser.add_argument("--mcp-base-url", default="http://127.0.0.1:9380")
    parser.add_argument("--mcp-mode", default="self-host")
    parser.add_argument("--mcp-host-api-key", default="")
    parser.add_argument("--mcp-script-path", default="/ragflow/mcp/server/server.py")
    parser.add_argument("--no-transport-sse-enabled", action="store_true")
    parser.add_argument("--no-transport-streamable-http-enabled", action="store_true")
    parser.add_argument("--no-json-response", action="store_true")
    args = parser.parse_args()
    if args.workers < 1 or args.consumer_no_beg < 0 or args.consumer_no_end < 0:
        parser.error("worker and consumer values must be positive")
    return args


def stop_children(*_args) -> None:
    STOP.set()
    for process in CHILDREN:
        if process.poll() is None:
            process.terminate()


def main() -> int:
    args = parse_arguments()
    signal.signal(signal.SIGTERM, stop_children)
    signal.signal(signal.SIGINT, stop_children)
    render_configuration()
    configure_nginx()
    ensure_docling()
    initialize_database()

    if args.init_model_provider_tables:
        subprocess.run(
            [
                PYTHON, "tools/scripts/mysql_migration.py", "--stages",
                "tenant_model_provider,tenant_model_instance,tenant_model,model_id_config",
                "--config", "conf/service_conf.yaml", "--execute",
                "--database-version", "v0.26.1", "--mark-database-version-on-success",
            ],
            cwd=ROOT,
            check=True,
        )

    scheme = os.environ.get("API_PROXY_SCHEME", "python").lower()
    python_enabled = scheme in {"python", "hybrid"}
    go_enabled = scheme in {"go", "hybrid"}

    if args.enable_adminserver:
        if python_enabled:
            start_loop([PYTHON, "admin/server/admin_server.py"])
        if go_enabled:
            start_loop(["bin/ragflow_server", "--admin"])

    if not args.disable_webserver:
        spawn(["/usr/sbin/nginx", "-g", "daemon off;"])
        if python_enabled:
            command = [PYTHON, "api/ragflow_server.py"]
            if args.init_superuser:
                command.append("--init-superuser")
            start_loop(command)
        if go_enabled:
            start_loop(["bin/ragflow_server", "--api"])

    if not args.disable_datasync:
        start_loop([PYTHON, "rag/svr/sync_data_source.py"])

    if args.enable_mcpserver:
        mcp_api_key = args.mcp_host_api_key or os.environ.get("RAGFLOW_MCP_HOST_API_KEY", "")
        command = [
            PYTHON, args.mcp_script_path, f"--host={args.mcp_host}", f"--port={args.mcp_port}",
            f"--base-url={args.mcp_base_url}", f"--mode={args.mcp_mode}", f"--api-key={mcp_api_key}",
            "--no-transport-sse-enabled" if args.no_transport_sse_enabled else "--transport-sse-enabled",
            "--no-transport-streamable-http-enabled" if args.no_transport_streamable_http_enabled else "--transport-streamable-http-enabled",
            "--no-json-response" if args.no_json_response else "--json-response",
        ]
        spawn(command)

    if not args.disable_taskexecutor:
        hostname = socket.gethostname()
        default_host_id = hostname if len(hostname) <= 32 else hashlib.md5(hostname.encode(), usedforsecurity=False).hexdigest()
        host_id = args.host_id or default_host_id
        begin, end = (args.consumer_no_beg, args.consumer_no_end) if args.consumer_no_end > args.consumer_no_beg else (0, args.workers)
        for consumer_id in range(begin, end):
            if python_enabled:
                start_loop(
                    [PYTHON, "rag/svr/task_executor.py", "-i", f"{host_id}_{consumer_id}", "-t", "common"],
                    environment=worker_environment(),
                )
            if go_enabled:
                start_loop(["bin/ragflow_server", "--ingestor"])
            time.sleep(1)

    while not STOP.wait(1):
        pass
    for process in CHILDREN:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
