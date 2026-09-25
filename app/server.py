"""Local web server for Transcritor. Only listens on this Mac (127.0.0.1)."""
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory

import formats
from engine import Engine

PORT = int(os.environ.get("TRANSCRITOR_PORT", "51789"))
HERE = Path(__file__).resolve().parent
OUT_DIR = Path(os.environ.get("TRANSCRITOR_OUT", Path.home() / "Documents" / "Transcritor"))
TMP_DIR = Path(tempfile.gettempdir()) / "transcritor-uploads"
IDLE_SHUTDOWN = 15 * 60  # quit after 15 min with no open window and nothing running

OUT_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, static_folder=None)
engine = Engine()
jobs = {}  # id -> dict
order = []
work = queue.Queue()
lock = threading.Lock()
last_ping = time.time()


def public(job):
    return {k: job[k] for k in ("id", "name", "status", "progress", "error", "language",
                                "duration", "started", "finished", "files", "queued_at")}


def unique_base(stem):
    base = OUT_DIR / stem
    n = 2
    while any(base.with_suffix(ext).exists() for ext in (".txt", ".docx", ".srt")):
        base = OUT_DIR / f"{stem} ({n})"
        n += 1
    return base


def worker():
    while True:
        job_id = work.get()
        job = jobs.get(job_id)
        if not job or job["status"] == "cancelled":
            continue
        job.update(status="running", started=time.time(), progress=0.0)
        try:
            def progress(p):
                job["progress"] = round(p, 4)

            result = engine.transcribe(job["path"], job["lang"], job["prompt"], progress)
            segs = result["segments"]
            stem = Path(job["name"]).stem
            base = unique_base(stem)
            txt = base.with_suffix(".txt")
            txt.write_text(formats.to_txt(segs), encoding="utf-8")
            timed = base.parent / (base.name + " - timestamps.txt")
            timed.write_text(formats.to_timestamped_txt(segs), encoding="utf-8")
            srt = base.with_suffix(".srt")
            srt.write_text(formats.to_srt(segs), encoding="utf-8")
            docx = base.with_suffix(".docx")
            formats.to_docx(segs, docx, stem, result["language"], result["duration"])
            job.update(
                status="done", progress=1.0, finished=time.time(),
                language=result["language"], duration=result["duration"],
                files={"txt": str(txt), "timed": str(timed), "srt": str(srt), "docx": str(docx)},
            )
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            text = str(e)
            if "NO_AUDIO" in text:
                msg = "NO_AUDIO"
            elif any(k in text for k in ("huggingface", "Connection", "403", "resolve", "offline")):
                msg = "NO_MODEL"
            else:
                msg = text[:300]
            job.update(status="error", error=msg, finished=time.time())
        finally:
            try:
                os.remove(job["path"])
            except OSError:
                pass


def idle_watch():
    while True:
        time.sleep(30)
        busy = any(j["status"] in ("queued", "running") for j in jobs.values())
        if not busy and time.time() - last_ping > IDLE_SHUTDOWN:
            os._exit(0)


@app.get("/")
def index():
    return send_from_directory(HERE / "static", "index.html")


@app.get("/ping")
def ping():
    global last_ping
    last_ping = time.time()
    return jsonify(ok=True, backend=engine.backend, out_dir=str(OUT_DIR))


@app.post("/upload")
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(error="no file"), 400
    job_id = uuid.uuid4().hex[:12]
    safe = Path(f.filename).name
    path = TMP_DIR / f"{job_id}{Path(safe).suffix}"
    f.save(path)
    lang = request.form.get("language") or None
    if lang == "auto":
        lang = None
    job = dict(id=job_id, name=safe, path=str(path), lang=lang,
               prompt=request.form.get("prompt", ""), status="queued", progress=0.0,
               error=None, language=None, duration=None, started=None, finished=None,
               files=None, queued_at=time.time())
    with lock:
        jobs[job_id] = job
        order.append(job_id)
    work.put(job_id)
    return jsonify(public(job))


@app.get("/jobs")
def list_jobs():
    return jsonify([public(jobs[i]) for i in reversed(order)])


@app.get("/jobs/<job_id>/text")
def job_text(job_id):
    job = jobs.get(job_id)
    if not job or job["status"] != "done":
        return jsonify(error="not ready"), 404
    return Path(job["files"]["txt"]).read_text(encoding="utf-8"), 200, {
        "Content-Type": "text/plain; charset=utf-8"}


@app.get("/jobs/<job_id>/file/<kind>")
def job_file(job_id, kind):
    job = jobs.get(job_id)
    if not job or job["status"] != "done" or kind not in job["files"]:
        return jsonify(error="not ready"), 404
    p = Path(job["files"][kind])
    return send_file(p, as_attachment=True, download_name=p.name)


@app.post("/jobs/<job_id>/cancel")
def cancel(job_id):
    job = jobs.get(job_id)
    if job and job["status"] == "queued":
        job["status"] = "cancelled"
    return jsonify(ok=True)


@app.post("/jobs/<job_id>/remove")
def remove(job_id):
    with lock:
        job = jobs.get(job_id)
        if job and job["status"] not in ("queued", "running"):
            jobs.pop(job_id, None)
            order.remove(job_id)
    return jsonify(ok=True)


@app.post("/reveal")
def reveal():
    job = jobs.get(request.json.get("id", "")) if request.is_json else None
    target = job["files"]["docx"] if job and job.get("files") else str(OUT_DIR)
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-R", target] if job else ["open", target])
    return jsonify(ok=True)


@app.post("/quit")
def quit_app():
    threading.Timer(0.5, lambda: os._exit(0)).start()
    return jsonify(ok=True)


if __name__ == "__main__":
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=idle_watch, daemon=True).start()
    app.run(host="127.0.0.1", port=PORT, threaded=True)
