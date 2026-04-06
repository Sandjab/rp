#!/usr/bin/env python3
"""Dashboard server: static file serving + variant API + pipeline orchestration with SSE.

Usage:
    python scripts/dashboard_server.py                # open browser on port 7432
    python scripts/dashboard_server.py --port 8080    # custom port
    python scripts/dashboard_server.py --no-browser   # don't open browser
    python scripts/dashboard_server.py --dev           # dev mode (CORS headers)
"""

import argparse
import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import yaml

# ── Paths ──────────────────────────────────────────────────────────────────────

PROJECT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_DIR / "scripts"
VARIANTS_DIR = PROJECT_DIR / ".pipeline" / "variants"
EDITORIAL_PATH = PROJECT_DIR / ".pipeline" / "02_editorial.json"
DIST_DIR = PROJECT_DIR / "dashboard" / "dist"
CONFIG_PATH = PROJECT_DIR / "config" / "revue-presse.yaml"
MANIFEST_PATH = PROJECT_DIR / "editions" / "archives" / "manifest.json"
PIPELINE_DIR = PROJECT_DIR / ".pipeline"

VARIANT_NAME_RE = re.compile(r"^[a-z0-9_]+$")

DEV_MODE = False  # set by --dev flag

# ── Variant helpers (reused from edit_variants_server.py) ──────────────────────


def file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.md5(path.read_bytes()).hexdigest()


def find_published() -> str | None:
    """Return the variant name whose content matches 02_editorial.json."""
    ref = file_hash(EDITORIAL_PATH)
    if ref is None:
        return None
    for f in sorted(VARIANTS_DIR.glob("editorial_*.json")):
        if hashlib.md5(f.read_bytes()).hexdigest() == ref:
            return f.stem.removeprefix("editorial_")
    return None


def list_variants() -> list[str]:
    if not VARIANTS_DIR.exists():
        return []
    names = []
    for f in sorted(VARIANTS_DIR.glob("editorial_*.json")):
        names.append(f.stem.removeprefix("editorial_"))
    return names


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


# ── Pipeline execution ─────────────────────────────────────────────────────────

PHASES = ["websearch", "collect", "editorial", "editor", "image", "html", "deploy"]

current_run: "PipelineRun | None" = None
run_lock = threading.Lock()


class PipelineRun:
    """Tracks a single pipeline execution with SSE event broadcasting."""

    def __init__(self, run_id: str, date: str, styles: list[str], options: dict):
        self.run_id = run_id
        self.date = date
        self.styles = styles
        self.options = options  # skip_collect, no_linkedin, no_deploy

        # Phase tracking
        self.phase_status: dict[str, str] = {}  # phase -> pending|running|done|error|skipped|paused|resumed
        self.phase_times: dict[str, dict] = {}  # phase -> {start, end, duration}
        self.current_phase: str | None = None
        self.running = True
        self.aborted = False
        self._process: subprocess.Popen | None = None

        # SSE events (append-only broadcast list)
        self._events: list[dict] = []
        self._events_lock = threading.Lock()

        # Initialize phase statuses
        for phase in PHASES:
            self.phase_status[phase] = "pending"

        # Mark skipped phases
        if options.get("skip_collect"):
            self.phase_status["websearch"] = "skipped"
            self.phase_status["collect"] = "skipped"
        if options.get("no_linkedin"):
            self.phase_status["image"] = "skipped"
        if options.get("no_deploy"):
            self.phase_status["deploy"] = "skipped"

    def emit(self, event: dict):
        """Append event to broadcast list (thread-safe)."""
        event.setdefault("timestamp", time.time())
        with self._events_lock:
            self._events.append(event)

    def get_events(self, cursor: int = 0) -> tuple[list[dict], int]:
        """Return events from cursor position. Returns (events, new_cursor)."""
        with self._events_lock:
            new_events = self._events[cursor:]
            return new_events, len(self._events)

    def run_phase_script(self, phase: str, cmd: list[str], env_extra: dict | None = None) -> bool:
        """Internal: run a subprocess for a phase, streaming output as SSE events."""
        if self.aborted:
            return False

        self.current_phase = phase
        self.phase_status[phase] = "running"
        start = time.time()
        self.phase_times[phase] = {"start": start}
        self.emit({"type": "phase_start", "phase": phase})

        env = os.environ.copy()
        env["RP_EDITION_DATE"] = self.date
        env["PYTHONUNBUFFERED"] = "1"
        if env_extra:
            env.update(env_extra)

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(PROJECT_DIR),
                env=env,
            )
            self._process = proc

            def stream_output(pipe, stream_name):
                for raw_line in iter(pipe.readline, b""):
                    if self.aborted:
                        break
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                    if line:
                        self.emit({"type": "log", "phase": phase, "stream": stream_name, "text": line})
                pipe.close()

            t_out = threading.Thread(target=stream_output, args=(proc.stdout, "stdout"), daemon=True)
            t_err = threading.Thread(target=stream_output, args=(proc.stderr, "stderr"), daemon=True)
            t_out.start()
            t_err.start()

            proc.wait()
            t_out.join(timeout=5)
            t_err.join(timeout=5)

            rc = proc.returncode
            self._process = None

            end = time.time()
            self.phase_times[phase]["end"] = end
            self.phase_times[phase]["duration"] = round(end - start, 2)

            if self.aborted:
                self.phase_status[phase] = "error"
                self.emit({"type": "phase_error", "phase": phase, "error": "Aborted"})
                return False

            if rc != 0:
                self.phase_status[phase] = "error"
                self.emit({"type": "phase_error", "phase": phase, "error": f"Exit code {rc}"})
                return False

            self.phase_status[phase] = "done"
            self.emit({"type": "phase_done", "phase": phase})
            return True

        except Exception as e:
            end = time.time()
            self.phase_times[phase]["end"] = end
            self.phase_times[phase]["duration"] = round(end - start, 2)
            self.phase_status[phase] = "error"
            self.emit({"type": "phase_error", "phase": phase, "error": str(e)})
            self._process = None
            return False

    def _pause_phase(self, phase: str):
        """Pause a phase and wait for resume or abort."""
        self.current_phase = phase
        self.phase_status[phase] = "paused"
        self.emit({"type": "pause", "phase": phase})

        while self.phase_status[phase] == "paused" and not self.aborted:
            time.sleep(0.3)

        if self.aborted:
            self.phase_status[phase] = "error"
            self.emit({"type": "phase_error", "phase": phase, "error": "Aborted"})
            return False

        # status was set to "resumed" by the resume endpoint
        return True

    def run_pipeline(self):
        """Execute all pipeline phases in sequence."""
        python = sys.executable

        try:
            # Ensure .pipeline directory exists
            PIPELINE_DIR.mkdir(parents=True, exist_ok=True)

            # ── Phase: websearch ──
            if self.phase_status["websearch"] != "skipped":
                ok = self.run_phase_script(
                    "websearch",
                    [python, str(SCRIPTS_DIR / "websearch_collect.py")],
                )
                if not ok and not self.aborted:
                    # WebSearch is tolerant - continue on failure
                    self.emit({"type": "log", "phase": "websearch", "stream": "stderr",
                               "text": "[WARN] WebSearch failed, continuing with RSS only"})

            if self.aborted:
                self._finish_pipeline()
                return

            # ── Phase: collect ──
            if self.phase_status["collect"] != "skipped":
                ok = self.run_phase_script(
                    "collect",
                    [python, str(SCRIPTS_DIR / "collect.py")],
                )
                if not ok:
                    self._finish_pipeline()
                    return

            if self.aborted:
                self._finish_pipeline()
                return

            # ── Phase: editorial (one run per style) ──
            if self.phase_status["editorial"] != "skipped":
                self.current_phase = "editorial"
                self.phase_status["editorial"] = "running"
                editorial_start = time.time()
                self.phase_times["editorial"] = {"start": editorial_start}
                self.emit({"type": "phase_start", "phase": "editorial"})

                VARIANTS_DIR.mkdir(parents=True, exist_ok=True)
                generated_styles = []

                for style in self.styles:
                    if self.aborted:
                        break

                    sub_phase = f"editorial_{style}"
                    self.emit({"type": "log", "phase": "editorial", "stream": "stdout",
                               "text": f"── Generating variant: {style} ──"})

                    ok = self.run_phase_script(
                        sub_phase,
                        [python, str(SCRIPTS_DIR / "write_editorial.py")],
                        env_extra={"EDITO_STYLE": style},
                    )

                    if ok:
                        # Copy to variants directory
                        src = EDITORIAL_PATH
                        dst = VARIANTS_DIR / f"editorial_{style}.json"
                        if src.exists():
                            shutil.copy2(src, dst)
                            generated_styles.append(style)
                            self.emit({"type": "log", "phase": "editorial", "stream": "stdout",
                                       "text": f"[OK] Variant '{style}' saved"})
                    else:
                        self.emit({"type": "log", "phase": "editorial", "stream": "stderr",
                                   "text": f"[WARN] Variant '{style}' failed"})

                editorial_end = time.time()
                self.phase_times["editorial"]["end"] = editorial_end
                self.phase_times["editorial"]["duration"] = round(editorial_end - editorial_start, 2)

                if not generated_styles:
                    self.phase_status["editorial"] = "error"
                    self.emit({"type": "phase_error", "phase": "editorial", "error": "No variants generated"})
                    self._finish_pipeline()
                    return

                self.phase_status["editorial"] = "done"
                self.emit({"type": "phase_done", "phase": "editorial"})

            if self.aborted:
                self._finish_pipeline()
                return

            # ── Phase: editor (interactive pause) ──
            if self.phase_status["editor"] != "skipped":
                resumed = self._pause_phase("editor")
                if not resumed:
                    self._finish_pipeline()
                    return
                self.phase_status["editor"] = "done"
                self.emit({"type": "phase_done", "phase": "editor"})

            if self.aborted:
                self._finish_pipeline()
                return

            # ── Phase: image (interactive pause for LinkedIn image) ──
            if self.phase_status["image"] != "skipped":
                resumed = self._pause_phase("image")
                if not resumed:
                    self._finish_pipeline()
                    return
                self.phase_status["image"] = "done"
                self.emit({"type": "phase_done", "phase": "image"})

            if self.aborted:
                self._finish_pipeline()
                return

            # ── Phase: html ──
            if self.phase_status["html"] != "skipped":
                ok = self.run_phase_script(
                    "html",
                    [python, str(SCRIPTS_DIR / "generate_edition.py"),
                     str(EDITORIAL_PATH)],
                )
                if not ok:
                    self._finish_pipeline()
                    return

            if self.aborted:
                self._finish_pipeline()
                return

            # ── Phase: deploy (interactive pause, then run) ──
            if self.phase_status["deploy"] != "skipped":
                resumed = self._pause_phase("deploy")
                if not resumed:
                    self._finish_pipeline()
                    return

                ok = self.run_phase_script(
                    "deploy",
                    [python, str(SCRIPTS_DIR / "deploy.py")],
                )
                if not ok:
                    self._finish_pipeline()
                    return

        except Exception as e:
            self.emit({"type": "log", "phase": self.current_phase or "unknown",
                       "stream": "stderr", "text": f"Pipeline error: {e}"})
        finally:
            self._finish_pipeline()

    def _finish_pipeline(self):
        """Mark pipeline as done and emit final event (idempotent)."""
        if not self.running:
            return  # already finished
        self.running = False
        self.current_phase = None
        self.emit({"type": "pipeline_done", "aborted": self.aborted})

    def abort(self):
        """Abort the running pipeline."""
        self.aborted = True
        proc = self._process
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def status_dict(self) -> dict:
        """Return pipeline status as a dict."""
        return {
            "running": self.running,
            "run_id": self.run_id,
            "current_phase": self.current_phase,
            "phase_status": self.phase_status,
            "phase_times": self.phase_times,
            "date": self.date,
            "styles": self.styles,
            "aborted": self.aborted,
        }


# ── HTTP Handler ───────────────────────────────────────────────────────────────

class DashboardHandler(BaseHTTPRequestHandler):

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        if DEV_MODE:
            self._add_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status, message):
        self._send_json({"error": message}, status)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length)

    def _add_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(204)
        self._add_cors_headers()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        # ── Variant API ────────────────────────────────────────────────────
        if path == "/api/variants":
            self._send_json({
                "variants": list_variants(),
                "published": find_published(),
            })
            return

        if path.startswith("/api/variant/"):
            name = path.removeprefix("/api/variant/")
            if not VARIANT_NAME_RE.match(name):
                self._send_error(400, "Invalid variant name")
                return
            fpath = VARIANTS_DIR / f"editorial_{name}.json"
            if not fpath.exists():
                self._send_error(404, f"Variant '{name}' not found")
                return
            data = json.loads(fpath.read_text("utf-8"))
            self._send_json(data)
            return

        if path == "/api/current":
            if not EDITORIAL_PATH.exists():
                self._send_error(404, "02_editorial.json not found")
                return
            data = json.loads(EDITORIAL_PATH.read_text("utf-8"))
            self._send_json(data)
            return

        # ── Edition/next API ───────────────────────────────────────────────
        if path == "/api/edition/next":
            self._handle_edition_next()
            return

        # ── Pipeline API ───────────────────────────────────────────────────
        if path == "/api/pipeline/status":
            self._handle_pipeline_status()
            return

        if path == "/api/pipeline/events":
            self._handle_pipeline_events()
            return

        # ── Static file serving (SPA fallback) ─────────────────────────────
        self._serve_static(path)

    def do_POST(self):
        path = urlparse(self.path).path

        # ── Variant API ────────────────────────────────────────────────────
        if path.startswith("/api/variant/"):
            name = path.removeprefix("/api/variant/")
            if not VARIANT_NAME_RE.match(name):
                self._send_error(400, "Invalid variant name")
                return
            fpath = VARIANTS_DIR / f"editorial_{name}.json"
            if not fpath.exists():
                self._send_error(404, f"Variant '{name}' not found")
                return
            try:
                data = json.loads(self._read_body())
            except json.JSONDecodeError as e:
                self._send_error(400, f"Invalid JSON: {e}")
                return
            if not isinstance(data, list):
                self._send_error(400, "Expected JSON array")
                return
            fpath.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self._send_json({"ok": True})
            return

        if path.startswith("/api/publish/"):
            name = path.removeprefix("/api/publish/")
            if not VARIANT_NAME_RE.match(name):
                self._send_error(400, "Invalid variant name")
                return
            fpath = VARIANTS_DIR / f"editorial_{name}.json"
            if not fpath.exists():
                self._send_error(404, f"Variant '{name}' not found")
                return
            shutil.copy2(fpath, EDITORIAL_PATH)
            self._send_json({"ok": True, "published": name})
            return

        # ── Pipeline API ───────────────────────────────────────────────────
        if path == "/api/pipeline/start":
            self._handle_pipeline_start()
            return

        if path == "/api/pipeline/resume":
            self._handle_pipeline_resume()
            return

        if path == "/api/pipeline/abort":
            self._handle_pipeline_abort()
            return

        self._send_error(404, "Not found")

    # ── Edition/next ───────────────────────────────────────────────────────

    def _handle_edition_next(self):
        config = load_config()
        tz = ZoneInfo(config.get("edition", {}).get("timezone", "Europe/Paris"))

        # Count unique dates from manifest
        unique_dates = set()
        if MANIFEST_PATH.exists():
            try:
                entries = json.loads(MANIFEST_PATH.read_text("utf-8"))
                for entry in entries:
                    d = entry.get("date", "")
                    if d:
                        unique_dates.add(d)
            except (json.JSONDecodeError, KeyError):
                pass

        number = len(unique_dates) + 1
        tomorrow = datetime.now(tz) + timedelta(days=1)
        date_str = tomorrow.strftime("%Y-%m-%d")
        title = config.get("edition", {}).get("title", "IA qu'a demander")
        styles = ["deep", "angle", "focused"]

        self._send_json({
            "number": number,
            "date": date_str,
            "title": title,
            "styles": styles,
        })

    # ── Pipeline status ────────────────────────────────────────────────────

    def _handle_pipeline_status(self):
        global current_run
        if current_run is None:
            self._send_json({"running": False, "run_id": None})
            return
        self._send_json(current_run.status_dict())

    # ── Pipeline start ─────────────────────────────────────────────────────

    def _handle_pipeline_start(self):
        global current_run

        with run_lock:
            if current_run is not None and current_run.running:
                self._send_error(409, "Pipeline already running")
                return

            try:
                body = json.loads(self._read_body())
            except json.JSONDecodeError as e:
                self._send_error(400, f"Invalid JSON: {e}")
                return

            date = body.get("date", "")
            styles = body.get("styles", ["deep", "angle", "focused"])
            skip_collect = body.get("skip_collect", False)
            no_linkedin = body.get("no_linkedin", False)
            no_deploy = body.get("no_deploy", False)

            if not date:
                self._send_error(400, "Missing 'date' field")
                return

            run_id = f"run_{int(time.time())}_{os.getpid()}"
            current_run = PipelineRun(
                run_id=run_id,
                date=date,
                styles=styles,
                options={
                    "skip_collect": skip_collect,
                    "no_linkedin": no_linkedin,
                    "no_deploy": no_deploy,
                },
            )

            t = threading.Thread(target=current_run.run_pipeline, daemon=True)
            t.start()

        self._send_json({"ok": True, "run_id": run_id})

    # ── Pipeline resume ────────────────────────────────────────────────────

    def _handle_pipeline_resume(self):
        global current_run
        if current_run is None:
            self._send_error(404, "No pipeline running")
            return

        # Find the paused phase and resume it
        resumed_phase = None
        for phase in PHASES:
            if current_run.phase_status.get(phase) == "paused":
                current_run.phase_status[phase] = "resumed"
                resumed_phase = phase
                break

        if resumed_phase is None:
            self._send_error(400, "No phase is paused")
            return

        self._send_json({"ok": True, "resumed": resumed_phase})

    # ── Pipeline abort ─────────────────────────────────────────────────────

    def _handle_pipeline_abort(self):
        global current_run
        if current_run is None:
            self._send_error(404, "No pipeline running")
            return

        current_run.abort()
        self._send_json({"ok": True})

    # ── Pipeline SSE events ────────────────────────────────────────────────

    def _handle_pipeline_events(self):
        global current_run

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        if DEV_MODE:
            self._add_cors_headers()
        self.end_headers()

        if current_run is None:
            # No run active - send a single no_run event and close
            event_data = json.dumps({"type": "no_run"}, ensure_ascii=False)
            self.wfile.write(f"data: {event_data}\n\n".encode("utf-8"))
            self.wfile.flush()
            return

        cursor = 0
        run = current_run  # capture reference

        try:
            while True:
                events, cursor = run.get_events(cursor)
                for event in events:
                    event_data = json.dumps(event, ensure_ascii=False)
                    self.wfile.write(f"data: {event_data}\n\n".encode("utf-8"))
                    self.wfile.flush()

                    # Stop streaming after pipeline_done
                    if event.get("type") == "pipeline_done":
                        return

                # Send keepalive
                self.wfile.write(": keepalive\n\n".encode("utf-8"))
                self.wfile.flush()

                time.sleep(1)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError):
            pass  # client disconnected

    # ── Static file serving ────────────────────────────────────────────────

    def _serve_static(self, path: str):
        """Serve static files from dashboard/dist/ with SPA fallback."""
        # Normalize path
        if path == "/":
            path = "/index.html"

        # Resolve to filesystem path (prevent directory traversal)
        rel_path = path.lstrip("/")
        file_path = DIST_DIR / rel_path

        # Security: ensure resolved path is within DIST_DIR
        try:
            file_path = file_path.resolve()
            if not str(file_path).startswith(str(DIST_DIR.resolve())):
                self._send_error(403, "Forbidden")
                return
        except (OSError, ValueError):
            self._send_error(400, "Bad path")
            return

        # If file exists, serve it
        if file_path.is_file():
            self._serve_file(file_path)
            return

        # SPA fallback: any non-API, non-file route -> index.html
        index_path = DIST_DIR / "index.html"
        if index_path.is_file():
            self._serve_file(index_path)
        else:
            self._send_error(404, "Not found (no dashboard/dist/index.html)")

    def _serve_file(self, file_path: Path):
        """Serve a single file with appropriate content type."""
        content_type, _ = mimetypes.guess_type(str(file_path))
        if content_type is None:
            content_type = "application/octet-stream"

        try:
            body = file_path.read_bytes()
        except OSError:
            self._send_error(500, "Failed to read file")
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(body))
        if DEV_MODE:
            self._add_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """Keep logs concise: suppress API requests."""
        msg = args[0] if args else ""
        if "/api/" in msg and "events" not in msg:
            return
        if msg.endswith(".js") or msg.endswith(".css") or msg.endswith(".svg"):
            return
        super().log_message(format, *args)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    global DEV_MODE

    parser = argparse.ArgumentParser(description="Dashboard server for IA qu'a demander")
    parser.add_argument("--port", type=int, default=7432, help="Port to listen on (default: 7432)")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser on startup")
    parser.add_argument("--dev", action="store_true", help="Dev mode (CORS headers for Vite proxy)")
    args = parser.parse_args()

    DEV_MODE = args.dev

    if not DIST_DIR.exists():
        print(f"Warning: {DIST_DIR} does not exist.")
        print("Run 'npm run build' in dashboard/ to create it.\n")

    url = f"http://127.0.0.1:{args.port}"
    server = HTTPServer(("127.0.0.1", args.port), DashboardHandler)
    print(f"Dashboard server: {url}")

    if DEV_MODE:
        print("Dev mode: CORS headers enabled")

    if not args.no_browser:
        webbrowser.open_new_tab(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
