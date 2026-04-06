# Dashboard Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the shell-script-based editorial pipeline with a React + Python dashboard that orchestrates all phases, edits variants visually, generates images interactively, and deploys — all from a single browser tab.

**Architecture:** Vite + React + TypeScript frontend with shadcn/ui + Tailwind, served by an extended Python stdlib HTTP server. SSE for real-time log streaming. The server launches pipeline scripts as subprocesses and pipes their output to the browser.

**Tech Stack:** Vite, React 19, TypeScript, Tailwind CSS v4, shadcn/ui, Python 3.12+ stdlib (http.server, subprocess, threading)

**Spec:** `docs/superpowers/specs/2026-04-06-dashboard-design.md`

---

## Scope Note

This plan covers **Phase 1: Foundation + Production Tab** — the backend server, frontend scaffold, stepper with auto-execution, and the variant editor step. This gets the core pipeline orchestration working end-to-end.

**Phase 2** (Image step, Config tab, Archives tab, polish with impeccable) will be planned separately once Phase 1 is validated.

---

### Task 1: Scaffold the Vite + React + shadcn/ui project

**Files:**
- Create: `dashboard/package.json`
- Create: `dashboard/tsconfig.json`
- Create: `dashboard/tsconfig.app.json`
- Create: `dashboard/vite.config.ts`
- Create: `dashboard/index.html`
- Create: `dashboard/src/main.tsx`
- Create: `dashboard/src/App.tsx`
- Create: `dashboard/src/index.css`
- Create: `dashboard/components.json`
- Create: `dashboard/tailwind.config.ts` (if needed by shadcn — Tailwind v4 may use CSS config)

- [ ] **Step 1: Initialize the Vite project**

```bash
cd D:/DEV/ClaudeCode/rp
npm create vite@latest dashboard -- --template react-ts
cd dashboard
npm install
```

- [ ] **Step 2: Install Tailwind CSS v4**

```bash
cd D:/DEV/ClaudeCode/rp/dashboard
npm install tailwindcss @tailwindcss/vite
```

Update `vite.config.ts`:
```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:7432",
    },
  },
  build: {
    outDir: "dist",
  },
});
```

Update `src/index.css`:
```css
@import "tailwindcss";
```

- [ ] **Step 3: Initialize shadcn/ui**

```bash
cd D:/DEV/ClaudeCode/rp/dashboard
npx shadcn@latest init
```

Select: TypeScript, New York style, Zinc base color, CSS variables.

- [ ] **Step 4: Add required shadcn components**

```bash
npx shadcn@latest add button tabs badge card select checkbox textarea separator scroll-area sheet
```

- [ ] **Step 5: Create minimal App.tsx with tabs**

```tsx
// dashboard/src/App.tsx
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function App() {
  return (
    <div className="h-screen flex flex-col bg-background text-foreground">
      <header className="flex items-center gap-4 border-b px-6 py-3">
        <h1 className="font-serif text-xl">IA qu'à demander</h1>
        <span className="text-sm text-muted-foreground font-mono">
          Dashboard
        </span>
      </header>
      <Tabs defaultValue="production" className="flex-1 flex flex-col">
        <TabsList className="mx-6 mt-2 w-fit">
          <TabsTrigger value="production">Production</TabsTrigger>
          <TabsTrigger value="config">Config</TabsTrigger>
          <TabsTrigger value="archives">Archives</TabsTrigger>
        </TabsList>
        <TabsContent value="production" className="flex-1 p-6">
          <p className="text-muted-foreground">Production tab — stepper goes here</p>
        </TabsContent>
        <TabsContent value="config" className="flex-1 p-6">
          <p className="text-muted-foreground">Config tab — YAML editor goes here</p>
        </TabsContent>
        <TabsContent value="archives" className="flex-1 p-6">
          <p className="text-muted-foreground">Archives tab — edition list goes here</p>
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

- [ ] **Step 6: Verify the dev server starts**

```bash
cd D:/DEV/ClaudeCode/rp/dashboard
npm run dev
```

Open http://localhost:5173 — should see the header and 3 tabs.

- [ ] **Step 7: Build and verify output**

```bash
cd D:/DEV/ClaudeCode/rp/dashboard
npm run build
ls dist/
```

Should produce `dist/index.html` and `dist/assets/`.

- [ ] **Step 8: Commit**

```bash
git add dashboard/
echo "node_modules" >> dashboard/.gitignore
git add dashboard/.gitignore
git commit -m "feat: scaffold Vite + React + shadcn/ui dashboard"
```

---

### Task 2: Backend server — dashboard_server.py with static file serving + existing API

**Files:**
- Create: `scripts/dashboard_server.py`
- Reference: `scripts/edit_variants_server.py` (reuse patterns)

- [ ] **Step 1: Create dashboard_server.py with static serving + variant API**

```python
#!/usr/bin/env python3
"""Dashboard server — serves React frontend + API for pipeline orchestration.

Usage:
    python scripts/dashboard_server.py              # serve on port 7432
    python scripts/dashboard_server.py --port 8080  # custom port
    python scripts/dashboard_server.py --dev         # proxy mode (no static serving)
"""

import argparse
import hashlib
import json
import mimetypes
import re
import shutil
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
VARIANTS_DIR = PROJECT_DIR / ".pipeline" / "variants"
EDITORIAL_PATH = PROJECT_DIR / ".pipeline" / "02_editorial.json"
DIST_DIR = PROJECT_DIR / "dashboard" / "dist"

VARIANT_NAME_RE = re.compile(r"^[a-z0-9_]+$")


def file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.md5(path.read_bytes()).hexdigest()


def find_published() -> str | None:
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
    return [f.stem.removeprefix("editorial_")
            for f in sorted(VARIANTS_DIR.glob("editorial_*.json"))]


class DashboardHandler(BaseHTTPRequestHandler):

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status, message):
        self._send_json({"error": message}, status)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length)

    def _serve_static(self, url_path: str):
        """Serve a file from dashboard/dist/. SPA fallback to index.html."""
        # Strip leading /
        rel = url_path.lstrip("/")
        if not rel:
            rel = "index.html"
        file_path = DIST_DIR / rel
        if not file_path.is_file():
            # SPA fallback
            file_path = DIST_DIR / "index.html"
        if not file_path.is_file():
            self._send_error(404, "Not found")
            return
        mime, _ = mimetypes.guess_type(str(file_path))
        if mime is None:
            mime = "application/octet-stream"
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # --- API routes ---
        if self.path == "/api/variants":
            self._send_json({"variants": list_variants(), "published": find_published()})
            return
        if self.path.startswith("/api/variant/"):
            name = self.path.removeprefix("/api/variant/")
            if not VARIANT_NAME_RE.match(name):
                return self._send_error(400, "Invalid variant name")
            fpath = VARIANTS_DIR / f"editorial_{name}.json"
            if not fpath.exists():
                return self._send_error(404, f"Variant '{name}' not found")
            return self._send_json(json.loads(fpath.read_text("utf-8")))
        if self.path == "/api/current":
            if not EDITORIAL_PATH.exists():
                return self._send_error(404, "02_editorial.json not found")
            return self._send_json(json.loads(EDITORIAL_PATH.read_text("utf-8")))

        # --- Static files (SPA) ---
        if not self.path.startswith("/api/"):
            return self._serve_static(self.path)

        self._send_error(404, "Not found")

    def do_POST(self):
        if self.path.startswith("/api/variant/"):
            name = self.path.removeprefix("/api/variant/")
            if not VARIANT_NAME_RE.match(name):
                return self._send_error(400, "Invalid variant name")
            fpath = VARIANTS_DIR / f"editorial_{name}.json"
            if not fpath.exists():
                return self._send_error(404, f"Variant '{name}' not found")
            try:
                data = json.loads(self._read_body())
            except json.JSONDecodeError as e:
                return self._send_error(400, f"Invalid JSON: {e}")
            if not isinstance(data, list):
                return self._send_error(400, "Expected JSON array")
            fpath.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            return self._send_json({"ok": True})

        if self.path.startswith("/api/publish/"):
            name = self.path.removeprefix("/api/publish/")
            if not VARIANT_NAME_RE.match(name):
                return self._send_error(400, "Invalid variant name")
            fpath = VARIANTS_DIR / f"editorial_{name}.json"
            if not fpath.exists():
                return self._send_error(404, f"Variant '{name}' not found")
            shutil.copy2(fpath, EDITORIAL_PATH)
            return self._send_json({"ok": True, "published": name})

        self._send_error(404, "Not found")

    def log_message(self, format, *args):
        if args and "/api/" in str(args[0]):
            return
        super().log_message(format, *args)


def main():
    parser = argparse.ArgumentParser(description="Dashboard server")
    parser.add_argument("--port", type=int, default=7432)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--dev", action="store_true",
                        help="Dev mode: don't serve static, use Vite proxy")
    args = parser.parse_args()

    if not args.dev and not DIST_DIR.exists():
        print(f"Warning: {DIST_DIR} not found. Run 'cd dashboard && npm run build' first.")
        print("Starting in API-only mode.\n")

    url = f"http://127.0.0.1:{args.port}"
    server = HTTPServer(("127.0.0.1", args.port), DashboardHandler)
    print(f"Dashboard: {url}")

    if not args.no_browser and not args.dev:
        webbrowser.open_new_tab(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test static serving with the built frontend**

```bash
cd D:/DEV/ClaudeCode/rp
python scripts/dashboard_server.py --no-browser &
sleep 2
curl -s http://127.0.0.1:7432/ | head -5
curl -s http://127.0.0.1:7432/api/variants
```

Expected: first curl returns HTML, second returns `{"variants":[...],"published":null}`.

- [ ] **Step 3: Commit**

```bash
git add scripts/dashboard_server.py
git commit -m "feat: add dashboard server with static serving + variant API"
```

---

### Task 3: API — edition/next endpoint

**Files:**
- Modify: `scripts/dashboard_server.py`

- [ ] **Step 1: Add edition/next endpoint**

Add this import at the top of `dashboard_server.py`:
```python
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import yaml
```

Add this function before the handler class:
```python
def load_config():
    config_path = PROJECT_DIR / "config" / "revue-presse.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_next_edition():
    """Compute next edition number and suggested date."""
    config = load_config()
    tz = ZoneInfo(config["edition"]["timezone"])
    tomorrow = (datetime.now(tz) + timedelta(days=1)).strftime("%Y-%m-%d")
    archives_dir = PROJECT_DIR / "editions" / "archives"
    manifest_path = archives_dir / "manifest.json"
    number = 1
    if manifest_path.exists():
        with open(manifest_path) as f:
            entries = json.load(f)
        if entries:
            unique_days = set(e.get("date", "") for e in entries)
            number = len(unique_days) + 1
    return {
        "number": number,
        "date": tomorrow,
        "title": config["edition"]["title"],
        "styles": ["deep", "angle", "focused"],
    }
```

Add this route in `do_GET`, before the static files block:
```python
        if self.path == "/api/edition/next":
            return self._send_json(get_next_edition())
```

- [ ] **Step 2: Test the endpoint**

```bash
curl -s http://127.0.0.1:7432/api/edition/next | python -m json.tool
```

Expected: `{"number": 9, "date": "2026-04-07", "title": "IA qu'à demander", "styles": ["deep", "angle", "focused"]}`.

- [ ] **Step 3: Commit**

```bash
git add scripts/dashboard_server.py
git commit -m "feat: add /api/edition/next endpoint"
```

---

### Task 4: API — pipeline execution with SSE

**Files:**
- Modify: `scripts/dashboard_server.py`

This is the core: launching scripts as subprocesses, streaming output via SSE, handling phase transitions.

- [ ] **Step 1: Add PipelineRun class and phase definitions**

Add these imports:
```python
import subprocess
import threading
import time
import uuid
from queue import Queue
```

Add after the existing functions:
```python
SCRIPTS_DIR = PROJECT_DIR / "scripts"

PHASE_ORDER = ["websearch", "collect", "editorial", "editor", "image", "html", "deploy"]

PHASE_DEFS = {
    "websearch": {"auto": True},
    "collect": {"auto": True},
    "editorial": {"auto": True, "repeat_for_styles": True},
    "editor": {"auto": False},
    "image": {"auto": False},
    "html": {"auto": True},
    "deploy": {"auto": False},
}


class PipelineRun:
    def __init__(self, date: str, styles: list[str], options: dict):
        self.run_id = uuid.uuid4().hex[:8]
        self.date = date
        self.styles = styles
        self.options = options  # skip_collect, no_linkedin, no_deploy
        self.phase_status: dict[str, str] = {}
        self.phase_times: dict[str, float] = {}
        self.current_phase: str | None = None
        self.process: subprocess.Popen | None = None
        self.event_queue: Queue = Queue()
        self.aborted = False

        # Initialize phase statuses
        for phase in PHASE_ORDER:
            if phase in ("websearch", "collect") and options.get("skip_collect"):
                self.phase_status[phase] = "skipped"
            elif phase == "image" and options.get("no_linkedin"):
                self.phase_status[phase] = "skipped"
            elif phase == "deploy" and options.get("no_deploy"):
                self.phase_status[phase] = "skipped"
            else:
                self.phase_status[phase] = "pending"

    def emit(self, event: dict):
        event.setdefault("timestamp", time.time())
        self.event_queue.put(event)

    def run_phase_script(self, phase: str, cmd: list[str], env_extra: dict | None = None):
        """Run a script, streaming stdout/stderr to event queue."""
        self.phase_status[phase] = "running"
        self.current_phase = phase
        self.emit({"type": "phase_start", "phase": phase})
        start = time.time()

        env = os.environ.copy()
        if env_extra:
            env.update(env_extra)

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                cwd=str(PROJECT_DIR),
            )

            def stream_pipe(pipe, stream_name):
                for line in pipe:
                    if self.aborted:
                        break
                    self.emit({"type": "log", "phase": phase,
                               "line": line.rstrip("\n"), "stream": stream_name})
                pipe.close()

            t_out = threading.Thread(target=stream_pipe, args=(self.process.stdout, "stdout"))
            t_err = threading.Thread(target=stream_pipe, args=(self.process.stderr, "stderr"))
            t_out.start()
            t_err.start()

            self.process.wait()
            t_out.join()
            t_err.join()

            duration = time.time() - start
            self.phase_times[phase] = duration
            exit_code = self.process.returncode

            if self.aborted:
                self.phase_status[phase] = "error"
                self.emit({"type": "phase_error", "phase": phase, "error": "Aborted"})
                return False

            if exit_code != 0:
                self.phase_status[phase] = "error"
                self.emit({"type": "phase_error", "phase": phase,
                           "error": f"Exit code {exit_code}", "duration_s": duration})
                return False

            self.phase_status[phase] = "done"
            self.emit({"type": "phase_done", "phase": phase,
                       "duration_s": duration, "exit_code": 0})
            return True

        except Exception as e:
            duration = time.time() - start
            self.phase_times[phase] = duration
            self.phase_status[phase] = "error"
            self.emit({"type": "phase_error", "phase": phase, "error": str(e)})
            return False
        finally:
            self.process = None

    def run_pipeline(self):
        """Run the full pipeline in a background thread."""
        py = sys.executable

        for phase in PHASE_ORDER:
            if self.aborted:
                break
            if self.phase_status[phase] == "skipped":
                continue

            phase_def = PHASE_DEFS[phase]

            if phase == "websearch":
                env = {"RP_EDITION_DATE": self.date}
                if not self.run_phase_script(phase, [py, str(SCRIPTS_DIR / "websearch_collect.py")], env):
                    # Websearch is tolerant — continue even on failure
                    self.phase_status[phase] = "done"
                    self.emit({"type": "log", "phase": phase,
                               "line": "[WARN] WebSearch failed, continuing with RSS only", "stream": "stderr"})

            elif phase == "collect":
                env = {"RP_EDITION_DATE": self.date, "RP_MAX_CANDIDATES": "25"}
                if not self.run_phase_script(phase, [py, str(SCRIPTS_DIR / "collect.py")], env):
                    break

            elif phase == "editorial":
                self.phase_status[phase] = "running"
                self.current_phase = phase
                self.emit({"type": "phase_start", "phase": phase})
                start = time.time()
                all_ok = True
                for style in self.styles:
                    if self.aborted:
                        break
                    self.emit({"type": "log", "phase": phase,
                               "line": f"Generating variant: {style}", "stream": "stdout"})
                    env = {
                        "RP_EDITION_DATE": self.date,
                        "EDITO_STYLE": style,
                        "PROMPT_VERSION": "v2",
                    }
                    cmd = [py, str(SCRIPTS_DIR / "write_editorial.py")]
                    ok = self.run_phase_script(f"editorial_{style}", cmd, env)
                    if not ok:
                        all_ok = False
                        break
                duration = time.time() - start
                self.phase_times[phase] = duration
                if all_ok and not self.aborted:
                    self.phase_status[phase] = "done"
                    self.emit({"type": "phase_done", "phase": phase, "duration_s": duration, "exit_code": 0})
                else:
                    self.phase_status[phase] = "error"
                    break

            elif not phase_def["auto"]:
                # Interactive phase — pause and wait for resume
                self.phase_status[phase] = "paused"
                self.current_phase = phase
                self.emit({"type": "pause", "phase": phase, "reason": "interactive"})
                # Block until resumed (the resume endpoint sets status back to "running")
                while self.phase_status[phase] == "paused" and not self.aborted:
                    time.sleep(0.3)
                if self.aborted:
                    break
                if phase == "deploy":
                    env = {"RP_EDITION_DATE": self.date}
                    if not self.run_phase_script(phase, [py, str(SCRIPTS_DIR / "deploy.py")], env):
                        break

            elif phase == "html":
                env = {"RP_EDITION_DATE": self.date}
                if not self.run_phase_script(phase, [py, str(SCRIPTS_DIR / "generate_edition.py")], env):
                    break

        if not self.aborted:
            self.current_phase = None
            self.emit({"type": "pipeline_done"})


# Global pipeline state
current_run: PipelineRun | None = None
```

- [ ] **Step 2: Add pipeline start, events, resume, abort endpoints**

Add in `do_POST`:
```python
        if self.path == "/api/pipeline/start":
            global current_run
            if current_run and current_run.current_phase:
                return self._send_error(409, "Pipeline already running")
            try:
                body = json.loads(self._read_body())
            except json.JSONDecodeError:
                return self._send_error(400, "Invalid JSON")
            run = PipelineRun(
                date=body.get("date", ""),
                styles=body.get("styles", ["deep", "angle", "focused"]),
                options={
                    "skip_collect": body.get("skip_collect", False),
                    "no_linkedin": body.get("no_linkedin", False),
                    "no_deploy": body.get("no_deploy", False),
                },
            )
            current_run = run
            thread = threading.Thread(target=run.run_pipeline, daemon=True)
            thread.start()
            return self._send_json({"ok": True, "run_id": run.run_id})

        if self.path == "/api/pipeline/resume":
            if not current_run:
                return self._send_error(404, "No pipeline running")
            phase = current_run.current_phase
            if phase and current_run.phase_status.get(phase) == "paused":
                current_run.phase_status[phase] = "resumed"
            return self._send_json({"ok": True})

        if self.path == "/api/pipeline/abort":
            if not current_run:
                return self._send_error(404, "No pipeline running")
            current_run.aborted = True
            if current_run.process:
                current_run.process.terminate()
            return self._send_json({"ok": True})
```

Add in `do_GET`:
```python
        if self.path == "/api/pipeline/events":
            return self._serve_sse()

        if self.path == "/api/pipeline/status":
            if not current_run:
                return self._send_json({"running": False})
            return self._send_json({
                "running": current_run.current_phase is not None,
                "run_id": current_run.run_id,
                "current_phase": current_run.current_phase,
                "phase_status": current_run.phase_status,
                "phase_times": current_run.phase_times,
            })
```

Add the SSE method to the handler class:
```python
    def _serve_sse(self):
        """Serve Server-Sent Events stream for pipeline progress."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        if not current_run:
            self.wfile.write(b"data: {\"type\":\"no_run\"}\n\n")
            self.wfile.flush()
            return

        run = current_run
        try:
            while True:
                try:
                    event = run.event_queue.get(timeout=1)
                    data = json.dumps(event, ensure_ascii=False)
                    self.wfile.write(f"data: {data}\n\n".encode())
                    self.wfile.flush()
                    if event.get("type") == "pipeline_done":
                        break
                except Exception:
                    # Queue timeout — send keepalive
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
```

- [ ] **Step 3: Test the pipeline endpoints**

```bash
# Start server
python scripts/dashboard_server.py --no-browser --dev &

# Check status
curl -s http://127.0.0.1:7432/api/pipeline/status

# Start a pipeline (will fail early since no RSS, but tests the mechanism)
curl -s -X POST http://127.0.0.1:7432/api/pipeline/start \
  -H "Content-Type: application/json" \
  -d '{"date":"2026-04-07","styles":["deep"],"skip_collect":true,"no_linkedin":true,"no_deploy":true}'
```

- [ ] **Step 4: Commit**

```bash
git add scripts/dashboard_server.py
git commit -m "feat: add pipeline execution engine with SSE streaming"
```

---

### Task 5: Frontend — shared types and API client

**Files:**
- Create: `dashboard/src/lib/types.ts`
- Create: `dashboard/src/lib/api.ts`

- [ ] **Step 1: Create types**

```ts
// dashboard/src/lib/types.ts

export type PhaseStatus = "pending" | "running" | "done" | "error" | "skipped" | "paused" | "resumed";

export type PhaseName = "websearch" | "collect" | "editorial" | "editor" | "image" | "html" | "deploy";

export const PHASE_ORDER: PhaseName[] = [
  "websearch", "collect", "editorial", "editor", "image", "html", "deploy",
];

export const PHASE_LABELS: Record<PhaseName, string> = {
  websearch: "WebSearch",
  collect: "Collecte",
  editorial: "Éditorial",
  editor: "Éditeur",
  image: "Image",
  html: "HTML",
  deploy: "Deploy",
};

export interface EditionInfo {
  number: number;
  date: string;
  title: string;
  styles: string[];
}

export interface PipelineStatus {
  running: boolean;
  run_id?: string;
  current_phase?: PhaseName | null;
  phase_status?: Record<string, PhaseStatus>;
  phase_times?: Record<string, number>;
}

export interface PipelineEvent {
  type: "phase_start" | "phase_done" | "phase_error" | "log" | "pause" | "pipeline_done" | "no_run";
  phase?: string;
  line?: string;
  stream?: "stdout" | "stderr";
  duration_s?: number;
  exit_code?: number;
  error?: string;
  reason?: string;
  timestamp?: number;
}

export interface VariantArticle {
  is_synthesis?: boolean;
  is_not_serious?: boolean;
  editorial_title?: string;
  editorial_summary?: string;
  title?: string;
  url?: string;
  source?: string;
  published?: string;
  matched_topics?: string[];
  [key: string]: unknown;
}
```

- [ ] **Step 2: Create API client**

```ts
// dashboard/src/lib/api.ts

import type { EditionInfo, PipelineStatus, VariantArticle } from "./types";

const BASE = "";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(body.error || res.statusText);
  }
  return res.json();
}

export const api = {
  // Edition
  getNextEdition: () => fetchJson<EditionInfo>("/api/edition/next"),

  // Pipeline
  getPipelineStatus: () => fetchJson<PipelineStatus>("/api/pipeline/status"),
  startPipeline: (params: {
    date: string;
    styles: string[];
    skip_collect?: boolean;
    no_linkedin?: boolean;
    no_deploy?: boolean;
  }) =>
    fetchJson<{ ok: boolean; run_id: string }>("/api/pipeline/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    }),
  resumePipeline: () =>
    fetchJson<{ ok: boolean }>("/api/pipeline/resume", { method: "POST" }),
  abortPipeline: () =>
    fetchJson<{ ok: boolean }>("/api/pipeline/abort", { method: "POST" }),

  // Variants
  getVariants: () =>
    fetchJson<{ variants: string[]; published: string | null }>("/api/variants"),
  getVariant: (name: string) => fetchJson<VariantArticle[]>(`/api/variant/${name}`),
  saveVariant: (name: string, data: VariantArticle[]) =>
    fetchJson<{ ok: boolean }>(`/api/variant/${name}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  publishVariant: (name: string) =>
    fetchJson<{ ok: boolean; published: string }>(`/api/publish/${name}`, {
      method: "POST",
    }),
};

export function subscribePipelineEvents(
  onEvent: (event: import("./types").PipelineEvent) => void,
): () => void {
  const source = new EventSource(`${BASE}/api/pipeline/events`);
  source.onmessage = (e) => {
    try {
      onEvent(JSON.parse(e.data));
    } catch {
      // ignore parse errors
    }
  };
  source.onerror = () => {
    // EventSource will auto-reconnect
  };
  return () => source.close();
}
```

- [ ] **Step 3: Commit**

```bash
cd D:/DEV/ClaudeCode/rp
git add dashboard/src/lib/
git commit -m "feat: add TypeScript types and API client for dashboard"
```

---

### Task 6: Frontend — Stepper component

**Files:**
- Create: `dashboard/src/components/production/Stepper.tsx`

- [ ] **Step 1: Build the vertical stepper**

```tsx
// dashboard/src/components/production/Stepper.tsx
import { Badge } from "@/components/ui/badge";
import { PHASE_ORDER, PHASE_LABELS, type PhaseName, type PhaseStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

interface StepperProps {
  phaseStatus: Record<string, PhaseStatus>;
  phaseTimes: Record<string, number>;
  currentPhase: PhaseName | null;
  editionNumber: number;
  editionDate: string;
}

const STATUS_ICONS: Record<PhaseStatus, string> = {
  pending: "",
  running: "●",
  done: "✓",
  error: "✗",
  skipped: "—",
  paused: "⏸",
  resumed: "●",
};

const STATUS_COLORS: Record<PhaseStatus, string> = {
  pending: "bg-muted text-muted-foreground",
  running: "bg-red-500 text-white animate-pulse",
  done: "bg-emerald-600 text-white",
  error: "bg-destructive text-destructive-foreground",
  skipped: "bg-muted text-muted-foreground",
  paused: "bg-amber-500 text-white",
  resumed: "bg-red-500 text-white animate-pulse",
};

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m${s.toString().padStart(2, "0")}s`;
}

export function Stepper({ phaseStatus, phaseTimes, currentPhase, editionNumber, editionDate }: StepperProps) {
  return (
    <div className="flex flex-col gap-1 w-[160px] shrink-0">
      <div className="text-xs font-mono text-muted-foreground uppercase tracking-wider mb-2">
        Étapes
      </div>
      {PHASE_ORDER.map((phase, i) => {
        const status = phaseStatus[phase] || "pending";
        const time = phaseTimes[phase];
        const isCurrent = phase === currentPhase;
        return (
          <div
            key={phase}
            className={cn(
              "flex items-center gap-2 px-2 py-1.5 rounded text-sm transition-colors",
              isCurrent && "bg-accent/10",
              status === "skipped" && "opacity-40",
            )}
          >
            <span
              className={cn(
                "w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-mono shrink-0",
                STATUS_COLORS[status],
              )}
            >
              {status === "pending" ? i + 1 : STATUS_ICONS[status]}
            </span>
            <span className={cn("flex-1 truncate", isCurrent && "font-semibold")}>
              {PHASE_LABELS[phase]}
            </span>
            {time !== undefined && (
              <span className="text-[10px] font-mono text-muted-foreground">
                {formatDuration(time)}
              </span>
            )}
          </div>
        );
      })}
      <div className="mt-auto pt-4 border-t text-[11px] font-mono text-muted-foreground">
        Édition #{editionNumber} · {editionDate}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/src/components/production/Stepper.tsx
git commit -m "feat: add vertical stepper component"
```

---

### Task 7: Frontend — StepLauncher (pipeline start form)

**Files:**
- Create: `dashboard/src/components/production/StepLauncher.tsx`

- [ ] **Step 1: Build the launcher form**

```tsx
// dashboard/src/components/production/StepLauncher.tsx
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import type { EditionInfo } from "@/lib/types";

interface StepLauncherProps {
  edition: EditionInfo;
  onStart: (params: {
    date: string;
    styles: string[];
    skip_collect: boolean;
    no_linkedin: boolean;
    no_deploy: boolean;
  }) => void;
}

export function StepLauncher({ edition, onStart }: StepLauncherProps) {
  const [date, setDate] = useState(edition.date);
  const [styles, setStyles] = useState<string[]>(edition.styles);
  const [skipCollect, setSkipCollect] = useState(false);
  const [noLinkedin, setNoLinkedin] = useState(false);
  const [noDeploy, setNoDeploy] = useState(false);

  const toggleStyle = (s: string) => {
    setStyles((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s],
    );
  };

  const formattedDate = new Date(date + "T00:00:00").toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <div className="max-w-lg mx-auto flex flex-col gap-6 py-12">
      <div className="text-center">
        <h2 className="font-serif text-3xl mb-2">
          Édition #{edition.number}
        </h2>
        <p className="text-muted-foreground">
          {formattedDate}
        </p>
      </div>

      <div className="flex flex-col gap-4">
        <label className="text-sm font-medium">Date de parution</label>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="border rounded px-3 py-2 font-mono text-sm bg-background"
        />
      </div>

      <div className="flex flex-col gap-2">
        <label className="text-sm font-medium">Styles éditoriaux</label>
        <div className="flex gap-2">
          {["deep", "angle", "focused"].map((s) => (
            <Badge
              key={s}
              variant={styles.includes(s) ? "default" : "outline"}
              className="cursor-pointer select-none"
              onClick={() => toggleStyle(s)}
            >
              {s}
            </Badge>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <label className="text-sm font-medium">Options</label>
        <label className="flex items-center gap-2 text-sm">
          <Checkbox checked={skipCollect} onCheckedChange={(c) => setSkipCollect(!!c)} />
          Passer la collecte (réutiliser les candidats existants)
        </label>
        <label className="flex items-center gap-2 text-sm">
          <Checkbox checked={noLinkedin} onCheckedChange={(c) => setNoLinkedin(!!c)} />
          Sans image LinkedIn
        </label>
        <label className="flex items-center gap-2 text-sm">
          <Checkbox checked={noDeploy} onCheckedChange={(c) => setNoDeploy(!!c)} />
          Sans deploy
        </label>
      </div>

      <Button
        size="lg"
        className="mt-4"
        disabled={styles.length === 0}
        onClick={() =>
          onStart({
            date,
            styles,
            skip_collect: skipCollect,
            no_linkedin: noLinkedin,
            no_deploy: noDeploy,
          })
        }
      >
        Lancer l'édition #{edition.number}
      </Button>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/src/components/production/StepLauncher.tsx
git commit -m "feat: add pipeline launcher form component"
```

---

### Task 8: Frontend — StepEditor (variant editor in React)

**Files:**
- Create: `dashboard/src/components/production/StepEditor.tsx`

- [ ] **Step 1: Build the variant editor**

```tsx
// dashboard/src/components/production/StepEditor.tsx
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { VariantArticle } from "@/lib/types";
import { cn } from "@/lib/utils";

interface StepEditorProps {
  onPublishAndContinue: () => void;
}

export function StepEditor({ onPublishAndContinue }: StepEditorProps) {
  const [variants, setVariants] = useState<Record<string, VariantArticle[]>>({});
  const [names, setNames] = useState<string[]>([]);
  const [published, setPublished] = useState<string | null>(null);
  const [dirty, setDirty] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [status, setStatus] = useState("");

  useEffect(() => {
    loadVariants();
  }, []);

  async function loadVariants() {
    const info = await api.getVariants();
    setNames(info.variants);
    setPublished(info.published);
    const data: Record<string, VariantArticle[]> = {};
    for (const name of info.variants) {
      data[name] = await api.getVariant(name);
    }
    setVariants(data);
  }

  function updateField(name: string, field: "editorial_title" | "editorial_summary", value: string) {
    setVariants((prev) => {
      const copy = { ...prev };
      copy[name] = [...copy[name]];
      copy[name][0] = { ...copy[name][0], [field]: value };
      return copy;
    });
    setDirty((prev) => ({ ...prev, [name]: true }));
  }

  async function save(name: string) {
    setSaving(name);
    await api.saveVariant(name, variants[name]);
    setDirty((prev) => ({ ...prev, [name]: false }));
    setSaving(null);
    setStatus(`${name} enregistré`);
  }

  async function publishAndContinue(name: string) {
    if (dirty[name]) await save(name);
    await api.publishVariant(name);
    setPublished(name);
    setStatus(`${name} publié`);
    onPublishAndContinue();
  }

  // Ctrl+S
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        const focused = document.activeElement?.closest("[data-variant]") as HTMLElement;
        const name = focused?.dataset.variant;
        if (name && dirty[name]) save(name);
      }
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [dirty, variants]);

  if (names.length === 0) {
    return <p className="text-muted-foreground p-8">Aucune variante disponible.</p>;
  }

  return (
    <div className="flex flex-col h-full">
      {status && (
        <div className="text-xs font-mono text-muted-foreground px-4 py-1 border-b">
          {status}
        </div>
      )}
      <div className="flex flex-1 min-h-0">
        {names.map((name) => {
          const synthesis = variants[name]?.[0];
          if (!synthesis) return null;
          return (
            <div
              key={name}
              data-variant={name}
              className={cn(
                "flex-1 flex flex-col border-r last:border-r-0 min-w-0",
                dirty[name] && "bg-amber-500/5",
              )}
            >
              {/* Column header */}
              <div className={cn(
                "flex items-center gap-2 px-4 py-2 border-b shrink-0",
                published === name && "border-b-emerald-600 border-b-2",
              )}>
                <span className="font-mono text-sm font-semibold">{name}</span>
                {published === name && (
                  <span className="text-[10px] bg-emerald-600 text-white px-1.5 py-0.5 rounded font-mono">
                    publié
                  </span>
                )}
                <span className="flex-1" />
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs font-mono"
                  disabled={!dirty[name] || saving === name}
                  onClick={() => save(name)}
                >
                  {saving === name ? "..." : "Enregistrer"}
                </Button>
                <Button
                  variant="default"
                  size="sm"
                  className="text-xs font-mono bg-emerald-600 hover:bg-emerald-700"
                  onClick={() => publishAndContinue(name)}
                >
                  Publier & Continuer →
                </Button>
              </div>

              {/* Content */}
              <div className="flex-1 flex flex-col gap-3 p-4 overflow-y-auto">
                <label className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">
                  Titre éditorial
                </label>
                <input
                  type="text"
                  value={synthesis.editorial_title || ""}
                  onChange={(e) => updateField(name, "editorial_title", e.target.value)}
                  placeholder="Titre éditorial..."
                  className="font-serif text-lg border border-transparent hover:border-border focus:border-ring focus:outline-none rounded px-2 py-1 bg-transparent"
                />
                <label className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">
                  Édito (synthèse)
                </label>
                <AutoResizeTextarea
                  value={synthesis.editorial_summary || ""}
                  onChange={(v) => updateField(name, "editorial_summary", v)}
                  placeholder="Texte éditorial..."
                  className="flex-1 text-sm leading-relaxed border border-transparent hover:border-border focus:border-ring focus:outline-none rounded px-2 py-1 bg-transparent resize-none min-h-[200px]"
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AutoResizeTextarea({
  value, onChange, className, placeholder,
}: {
  value: string; onChange: (v: string) => void; className?: string; placeholder?: string;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (ref.current) {
      ref.current.style.height = "auto";
      ref.current.style.height = ref.current.scrollHeight + "px";
    }
  }, [value]);
  return (
    <textarea
      ref={ref}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={className}
    />
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/src/components/production/StepEditor.tsx
git commit -m "feat: add variant editor React component"
```

---

### Task 9: Frontend — LogPanel and StepProgress

**Files:**
- Create: `dashboard/src/components/production/LogPanel.tsx`
- Create: `dashboard/src/components/production/StepProgress.tsx`

- [ ] **Step 1: Build LogPanel**

```tsx
// dashboard/src/components/production/LogPanel.tsx
import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { PipelineEvent } from "@/lib/types";
import { cn } from "@/lib/utils";

interface LogPanelProps {
  logs: PipelineEvent[];
}

export function LogPanel({ logs }: LogPanelProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs.length]);

  return (
    <ScrollArea className="h-full font-mono text-xs leading-relaxed">
      <div className="p-3 space-y-0.5">
        {logs.map((log, i) => {
          if (log.type === "log") {
            return (
              <div key={i} className={cn(log.stream === "stderr" && "text-amber-500")}>
                {log.line}
              </div>
            );
          }
          if (log.type === "phase_start") {
            return (
              <div key={i} className="text-blue-400 font-semibold mt-2">
                ▶ {log.phase}
              </div>
            );
          }
          if (log.type === "phase_done") {
            return (
              <div key={i} className="text-emerald-500">
                ✓ {log.phase} ({log.duration_s?.toFixed(1)}s)
              </div>
            );
          }
          if (log.type === "phase_error") {
            return (
              <div key={i} className="text-destructive font-semibold">
                ✗ {log.phase}: {log.error}
              </div>
            );
          }
          if (log.type === "pause") {
            return (
              <div key={i} className="text-amber-400 font-semibold">
                ⏸ {log.phase} — en attente
              </div>
            );
          }
          if (log.type === "pipeline_done") {
            return (
              <div key={i} className="text-emerald-400 font-semibold mt-2">
                ● Pipeline terminé
              </div>
            );
          }
          return null;
        })}
        <div ref={endRef} />
      </div>
    </ScrollArea>
  );
}
```

- [ ] **Step 2: Build StepProgress (shown during auto phases)**

```tsx
// dashboard/src/components/production/StepProgress.tsx
import { PHASE_LABELS, type PhaseName } from "@/lib/types";

interface StepProgressProps {
  phase: PhaseName;
  elapsed?: number;
}

export function StepProgress({ phase, elapsed }: StepProgressProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4">
      <div className="w-8 h-8 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
      <div className="text-lg font-medium">{PHASE_LABELS[phase]}</div>
      <div className="text-sm text-muted-foreground">En cours...</div>
      {elapsed !== undefined && (
        <div className="font-mono text-xs text-muted-foreground">
          {Math.round(elapsed)}s
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/components/production/LogPanel.tsx dashboard/src/components/production/StepProgress.tsx
git commit -m "feat: add log panel and step progress components"
```

---

### Task 10: Frontend — StepDeploy

**Files:**
- Create: `dashboard/src/components/production/StepDeploy.tsx`

- [ ] **Step 1: Build the deploy confirmation step**

```tsx
// dashboard/src/components/production/StepDeploy.tsx
import { useState } from "react";
import { Button } from "@/components/ui/button";

interface StepDeployProps {
  editionNumber: number;
  editionDate: string;
  onDeploy: () => void;
}

export function StepDeploy({ editionNumber, editionDate, onDeploy }: StepDeployProps) {
  const [confirming, setConfirming] = useState(false);

  function handleClick() {
    if (confirming) {
      onDeploy();
      setConfirming(false);
      return;
    }
    setConfirming(true);
    setTimeout(() => setConfirming(false), 3000);
  }

  return (
    <div className="flex flex-col items-center justify-center h-full gap-6">
      <h2 className="font-serif text-2xl">Déployer l'édition #{editionNumber}</h2>
      <p className="text-muted-foreground">
        Date : {editionDate}
      </p>
      <p className="text-sm text-muted-foreground">
        → https://sandjab.github.io/rp/
      </p>
      <Button
        size="lg"
        variant={confirming ? "destructive" : "default"}
        onClick={handleClick}
      >
        {confirming ? "Confirmer le deploy ?" : "Déployer"}
      </Button>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/src/components/production/StepDeploy.tsx
git commit -m "feat: add deploy confirmation step component"
```

---

### Task 11: Frontend — ProductionTab (orchestrator)

**Files:**
- Create: `dashboard/src/components/production/ProductionTab.tsx`
- Modify: `dashboard/src/App.tsx`

- [ ] **Step 1: Build the Production tab orchestrator**

```tsx
// dashboard/src/components/production/ProductionTab.tsx
import { useCallback, useEffect, useRef, useState } from "react";
import { api, subscribePipelineEvents } from "@/lib/api";
import type {
  EditionInfo,
  PhaseName,
  PhaseStatus,
  PipelineEvent,
} from "@/lib/types";
import { Stepper } from "./Stepper";
import { StepLauncher } from "./StepLauncher";
import { StepProgress } from "./StepProgress";
import { StepEditor } from "./StepEditor";
import { StepDeploy } from "./StepDeploy";
import { LogPanel } from "./LogPanel";
// Which interactive phases need a specific component
const INTERACTIVE_PHASES = new Set<PhaseName>(["editor", "image", "deploy"]);
const AUTO_PHASES = new Set<PhaseName>(["websearch", "collect", "editorial", "html"]);

export function ProductionTab() {
  const [edition, setEdition] = useState<EditionInfo | null>(null);
  const [running, setRunning] = useState(false);
  const [phaseStatus, setPhaseStatus] = useState<Record<string, PhaseStatus>>({});
  const [phaseTimes, setPhaseTimes] = useState<Record<string, number>>({});
  const [currentPhase, setCurrentPhase] = useState<PhaseName | null>(null);
  const [logs, setLogs] = useState<PipelineEvent[]>([]);
  const [pipelineDone, setPipelineDone] = useState(false);
  const unsubRef = useRef<(() => void) | null>(null);

  // Load edition info
  useEffect(() => {
    api.getNextEdition().then(setEdition);
    // Check if pipeline is already running
    api.getPipelineStatus().then((status) => {
      if (status.running) {
        setRunning(true);
        setPhaseStatus(status.phase_status || {});
        setPhaseTimes(status.phase_times || {});
        setCurrentPhase(status.current_phase as PhaseName || null);
        connectSSE();
      }
    });
  }, []);

  const connectSSE = useCallback(() => {
    if (unsubRef.current) unsubRef.current();
    unsubRef.current = subscribePipelineEvents((event) => {
      setLogs((prev) => [...prev, event]);
      if (event.type === "phase_start" && event.phase) {
        setCurrentPhase(event.phase as PhaseName);
        setPhaseStatus((prev) => ({ ...prev, [event.phase!]: "running" }));
      }
      if (event.type === "phase_done" && event.phase) {
        setPhaseStatus((prev) => ({ ...prev, [event.phase!]: "done" }));
        if (event.duration_s !== undefined) {
          setPhaseTimes((prev) => ({ ...prev, [event.phase!]: event.duration_s! }));
        }
      }
      if (event.type === "phase_error" && event.phase) {
        setPhaseStatus((prev) => ({ ...prev, [event.phase!]: "error" }));
      }
      if (event.type === "pause" && event.phase) {
        setCurrentPhase(event.phase as PhaseName);
        setPhaseStatus((prev) => ({ ...prev, [event.phase!]: "paused" }));
      }
      if (event.type === "pipeline_done") {
        setRunning(false);
        setCurrentPhase(null);
        setPipelineDone(true);
      }
    });
  }, []);

  async function handleStart(params: {
    date: string;
    styles: string[];
    skip_collect: boolean;
    no_linkedin: boolean;
    no_deploy: boolean;
  }) {
    setLogs([]);
    setPipelineDone(false);
    setRunning(true);
    // Pre-set skipped phases
    const initialStatus: Record<string, PhaseStatus> = {};
    if (params.skip_collect) {
      initialStatus.websearch = "skipped";
      initialStatus.collect = "skipped";
    }
    if (params.no_linkedin) initialStatus.image = "skipped";
    if (params.no_deploy) initialStatus.deploy = "skipped";
    setPhaseStatus(initialStatus);

    await api.startPipeline(params);
    connectSSE();
  }

  async function handleResume() {
    await api.resumePipeline();
  }

  function renderContextualContent() {
    if (!running && !pipelineDone) {
      if (!edition) return null;
      return <StepLauncher edition={edition} onStart={handleStart} />;
    }

    if (!currentPhase) {
      if (pipelineDone) {
        return (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <h2 className="font-serif text-2xl mb-2">Pipeline terminé</h2>
              <p className="text-muted-foreground">
                Édition #{edition?.number} prête.
              </p>
            </div>
          </div>
        );
      }
      return null;
    }

    if (currentPhase === "editor" && phaseStatus.editor === "paused") {
      return <StepEditor onPublishAndContinue={handleResume} />;
    }

    if (currentPhase === "deploy" && phaseStatus.deploy === "paused") {
      return (
        <StepDeploy
          editionNumber={edition?.number || 0}
          editionDate={edition?.date || ""}
          onDeploy={handleResume}
        />
      );
    }

    if (currentPhase === "image" && phaseStatus.image === "paused") {
      // Phase 2 — for now, show a placeholder + continue button
      return (
        <div className="flex flex-col items-center justify-center h-full gap-4">
          <p className="text-muted-foreground">Image step — Phase 2</p>
          <button
            className="px-4 py-2 bg-primary text-primary-foreground rounded"
            onClick={handleResume}
          >
            Passer → HTML
          </button>
        </div>
      );
    }

    // Auto phase running
    if (AUTO_PHASES.has(currentPhase)) {
      return <StepProgress phase={currentPhase} />;
    }

    return null;
  }

  return (
    <div className="flex h-full">
      {/* Stepper sidebar */}
      {(running || pipelineDone) && (
        <div className="border-r p-4">
          <Stepper
            phaseStatus={phaseStatus}
            phaseTimes={phaseTimes}
            currentPhase={currentPhase}
            editionNumber={edition?.number || 0}
            editionDate={edition?.date || ""}
          />
        </div>
      )}

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-h-0">
        <div className="flex-1 min-h-0">{renderContextualContent()}</div>

        {/* Log panel */}
        {logs.length > 0 && (
          <div className="h-[200px] border-t bg-card shrink-0">
            <LogPanel logs={logs} />
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Wire into App.tsx**

Replace the Production TabsContent in `App.tsx`:
```tsx
// Add import at top
import { ProductionTab } from "@/components/production/ProductionTab";

// Replace the production TabsContent
<TabsContent value="production" className="flex-1">
  <ProductionTab />
</TabsContent>
```

- [ ] **Step 3: Build, start server, and test end-to-end**

```bash
cd D:/DEV/ClaudeCode/rp/dashboard && npm run build
cd D:/DEV/ClaudeCode/rp && python scripts/dashboard_server.py
```

Open http://127.0.0.1:7432 — should see:
1. The launcher form with edition #9 and date 2026-04-07
2. Click "Lancer" → stepper appears, phases execute, logs stream
3. Pause at editor step → variant columns appear
4. Click "Publier & Continuer" → resumes to next phase

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/
git commit -m "feat: wire up Production tab with stepper, launcher, editor, and deploy"
```

---

### Task 12: Fix SSE queue — broadcast to multiple consumers

**Files:**
- Modify: `scripts/dashboard_server.py`

The current `event_queue` is a single Queue which only one SSE client can consume. If the page reloads, events are lost. Switch to a broadcast pattern.

- [ ] **Step 1: Replace Queue with broadcast list**

Replace the `event_queue` and `emit` in PipelineRun:
```python
class PipelineRun:
    def __init__(self, ...):
        # ... existing init ...
        self.events: list[dict] = []  # all events (append-only log)
        self._lock = threading.Lock()

    def emit(self, event: dict):
        event.setdefault("timestamp", time.time())
        with self._lock:
            self.events.append(event)
```

Update `_serve_sse` to read from the list:
```python
    def _serve_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        if not current_run:
            self.wfile.write(b"data: {\"type\":\"no_run\"}\n\n")
            self.wfile.flush()
            return

        run = current_run
        cursor = 0
        try:
            while True:
                with run._lock:
                    new_events = run.events[cursor:]
                    cursor = len(run.events)
                for event in new_events:
                    data = json.dumps(event, ensure_ascii=False)
                    self.wfile.write(f"data: {data}\n\n".encode())
                    self.wfile.flush()
                    if event.get("type") == "pipeline_done":
                        return
                if not new_events:
                    time.sleep(0.3)
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
```

- [ ] **Step 2: Commit**

```bash
git add scripts/dashboard_server.py
git commit -m "fix: use broadcast pattern for SSE events"
```

---

### Task 13: Add .gitignore entries + cleanup

**Files:**
- Modify: `dashboard/.gitignore`
- Modify: `.gitignore` (root)

- [ ] **Step 1: Update gitignore files**

`dashboard/.gitignore`:
```
node_modules
dist
```

Root `.gitignore` — add:
```
.superpowers/
```

- [ ] **Step 2: Final build + smoke test**

```bash
cd D:/DEV/ClaudeCode/rp/dashboard && npm run build
cd D:/DEV/ClaudeCode/rp && python scripts/dashboard_server.py --no-browser
# In another terminal:
curl -s http://127.0.0.1:7432/ | head -1
curl -s http://127.0.0.1:7432/api/edition/next
curl -s http://127.0.0.1:7432/api/variants
curl -s http://127.0.0.1:7432/api/pipeline/status
```

- [ ] **Step 3: Commit everything**

```bash
git add -A
git commit -m "feat: Phase 1 complete — dashboard with pipeline orchestration + variant editor"
```

---

## Verification Checklist

1. `cd dashboard && npm run build` — builds without error
2. `python scripts/dashboard_server.py` — starts, opens browser, shows the 3 tabs
3. Production tab shows launcher form with correct edition number (#9) and date
4. Click "Lancer" → stepper appears on left, auto phases execute with streaming logs
5. Pipeline pauses at "Éditeur" → 3 variant columns visible, editable
6. Click "Publier & Continuer →" → variant saved as `02_editorial.json`, pipeline resumes
7. Pipeline pauses at "Deploy" → confirmation button works
8. Ctrl+S saves the focused variant column
9. Page refresh during pipeline → SSE reconnects and shows full event history
10. Works on both Windows and macOS (no hardcoded paths, `sys.executable` for subprocesses)

---

## What's Deferred to Phase 2

- **StepImage** — full image generation with prompt editor, model selector, preview (currently placeholder "Passer" button)
- **Config tab** — YAML editor for `revue-presse.yaml`
- **Archives tab** — manifest viewer with edition history
- **Polish with impeccable** — animations, color refinement, responsive tweaks
- **Copy-to-clipboard** for LinkedIn post text
- **Cross-variant copy buttons** (copier titre/édito →) in the React editor
