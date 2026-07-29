import json
import os
import queue
import shutil
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
import secrets

from pipeline import build_scenes, assemble_video, MAX_SCENES, MAX_SCRIPT_CHARS
from audio_prep import prepare_reference_audio
import narration as narration_mod

DATA_DIR = os.environ.get("DATA_DIR", "/data")
JOBS_DIR = os.path.join(DATA_DIR, "jobs")
os.makedirs(JOBS_DIR, exist_ok=True)

APP_PASSWORD = os.environ.get("APP_PASSWORD", "").strip()

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50MB reference audio cap

app = FastAPI(title="Narrated Video Toolkit")
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not APP_PASSWORD:
            return await call_next(request)
        auth = request.headers.get("authorization", "")
        if auth.startswith("Basic "):
            import base64
            try:
                decoded = base64.b64decode(auth[6:]).decode()
                _, _, pw = decoded.partition(":")
                if secrets.compare_digest(pw, APP_PASSWORD):
                    return await call_next(request)
            except Exception:
                pass
        return HTMLResponse("Unauthorized", status_code=401, headers={"WWW-Authenticate": "Basic"})


app.add_middleware(BasicAuthMiddleware)

# ---- job store -------------------------------------------------------------

_jobs_lock = threading.Lock()
_jobs: dict[str, dict] = {}
_job_queue: "queue.Queue[str]" = queue.Queue()


def _job_dir(job_id: str) -> str:
    return os.path.join(JOBS_DIR, job_id)


def _save_meta(job_id: str):
    with open(os.path.join(_job_dir(job_id), "meta.json"), "w") as f:
        json.dump(_jobs[job_id], f, indent=2)


def _load_all_jobs():
    if not os.path.isdir(JOBS_DIR):
        return
    for job_id in sorted(os.listdir(JOBS_DIR)):
        meta_path = os.path.join(_job_dir(job_id), "meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path) as f:
                    _jobs[job_id] = json.load(f)
            except Exception:
                continue


def _update_job(job_id: str, **kwargs):
    with _jobs_lock:
        _jobs[job_id].update(kwargs)
        _save_meta(job_id)


def _worker_loop():
    while True:
        job_id = _job_queue.get()
        try:
            _run_job(job_id)
        except Exception as e:
            traceback.print_exc()
            _update_job(job_id, state="error", error=str(e))


def _run_job(job_id: str):
    job = _jobs[job_id]
    jdir = _job_dir(job_id)
    ref_audio = job["reference_audio_path"]
    clean_ref = os.path.join(jdir, "reference_clean.wav")

    _update_job(job_id, state="preparing_audio")
    prepare_reference_audio(ref_audio, clean_ref)

    scenes = build_scenes(job["title"], job["script"])
    _update_job(job_id, state="narration", scene_total=len(scenes), scene_done=0)

    def narration_progress(done, total):
        _update_job(job_id, scene_done=done, scene_total=total)

    scene_texts = [s.body for s in scenes]
    wavs = narration_mod.generate_narration(scene_texts, clean_ref, jdir, progress_cb=narration_progress)

    _update_job(job_id, state="rendering", scene_done=0, scene_total=len(scenes))

    def render_progress(done, total):
        _update_job(job_id, scene_done=done, scene_total=total)

    final_path = os.path.join(jdir, "final.mp4")
    duration = assemble_video(
        scenes, wavs, jdir, final_path,
        footer_text=job["title"] or "Narrated Training Video",
        progress_cb=render_progress,
    )

    _update_job(job_id, state="done", duration_seconds=duration, finished_at=datetime.now(timezone.utc).isoformat())


_worker_thread = threading.Thread(target=_worker_loop, daemon=True)
_worker_thread.start()
_load_all_jobs()
for _jid, _j in list(_jobs.items()):
    if _j.get("state") not in ("done", "error"):
        _update_job(_jid, state="error", error="Interrupted by app restart - please resubmit.")


# ---- routes -----------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    with _jobs_lock:
        jobs = sorted(_jobs.values(), key=lambda j: j["created_at"], reverse=True)
    return templates.TemplateResponse(request, "index.html", {"jobs": jobs, "max_scenes": MAX_SCENES})


@app.post("/jobs")
async def create_job(
    title: str = Form(""),
    script: str = Form(...),
    reference_audio: UploadFile = File(...),
):
    script = script.strip()
    if not script:
        raise HTTPException(400, "Script text is required.")
    if len(script) > MAX_SCRIPT_CHARS:
        raise HTTPException(400, f"Script too long (max {MAX_SCRIPT_CHARS} characters).")

    contents = await reference_audio.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, "Reference audio file too large (max 50MB).")
    if not contents:
        raise HTTPException(400, "Reference audio file is required.")

    try:
        build_scenes(title, script)  # validate scene count up front
    except ValueError as e:
        raise HTTPException(400, str(e))

    job_id = uuid.uuid4().hex[:12]
    jdir = _job_dir(job_id)
    os.makedirs(jdir, exist_ok=True)

    ext = os.path.splitext(reference_audio.filename or "")[1] or ".wav"
    ref_path = os.path.join(jdir, f"reference{ext}")
    with open(ref_path, "wb") as f:
        f.write(contents)

    with _jobs_lock:
        _jobs[job_id] = {
            "id": job_id,
            "title": title.strip(),
            "script": script,
            "reference_audio_path": ref_path,
            "state": "queued",
            "scene_done": 0,
            "scene_total": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "error": None,
        }
        _save_meta(job_id)

    _job_queue.put(job_id)
    return {"id": job_id}


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    return JSONResponse(job)


@app.get("/jobs/{job_id}/video")
def job_video(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job or job.get("state") != "done":
        raise HTTPException(404, "Video not ready.")
    path = os.path.join(_job_dir(job_id), "final.mp4")
    if not os.path.exists(path):
        raise HTTPException(404, "Video file missing.")
    filename = f"{(job['title'] or 'video').replace(' ', '_')}.mp4"
    return FileResponse(path, media_type="video/mp4", filename=filename)


@app.delete("/jobs/{job_id}")
def delete_job(job_id: str):
    with _jobs_lock:
        job = _jobs.pop(job_id, None)
    if not job:
        raise HTTPException(404, "Job not found.")
    shutil.rmtree(_job_dir(job_id), ignore_errors=True)
    return {"deleted": job_id}


@app.get("/health")
def health():
    return {"status": "ok"}
