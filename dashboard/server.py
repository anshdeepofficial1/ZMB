"""ZMB Dashboard — local control room for the Instagram Reels engine.

FastAPI + vanilla SPA (static/). Sab kuch local fallback ke saath kaam karta hai:
  - Instagram secrets na hone par bhi overview/render/state kaam karte hain.
  - /api/trigger  : run_cycle spawn (dry-run ya full) background process ke roop mein
  - /api/local/*  : real-time log tail (polling — SSE ki zaroorat nahi)
  - /api/story    : scenarios graph current node preview ke saath
  - /api/videos   : out/*.mp4 stream + download

Run:  python dashboard/server.py   →  http://127.0.0.1:8787
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import engine  # noqa: E402
from common import (  # noqa: E402
    CONFIG_PATH, EXAMPLE_CONFIG_PATH, OUT_DIR, SCENARIOS_PATH,
    STATE_PATH, load_config, load_json, load_state,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
RUNS_DIR = OUT_DIR / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="ZMB Dashboard", version="2.0")
_runs: dict[str, dict] = {}  # id -> {proc, meta}

# GitHub Actions runs (agar gh CLI up hai) — non-fatal
WORKFLOW = ".github/workflows/episode.yml"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_name(name: str) -> str:
    """Path-traversal guard for file names served from out/."""
    name = Path(name).name
    if not name or name.startswith("."):
        raise HTTPException(400, "bad file name")
    return name


# ---------------------------------------------------------------- Runspawner
def _start_run(mode: str) -> str:
    rid = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    rdir = RUNS_DIR / rid
    rdir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "scripts/run_cycle.py"]
    if mode == "dry":
        cmd.append("--dry-run")
    elif mode == "stills":
        cmd.extend(["--dry-run", "--stills"])
    proc = subprocess.Popen(
        cmd, cwd=str(ROOT), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding="utf-8",
        errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        bufsize=1, env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    _runs[rid] = {"proc": proc, "mode": mode, "started": _now()}
    log_path = rdir / "log.txt"

    def _tee():
        with open(log_path, "w", encoding="utf-8", errors="replace") as f:
            for line in proc.stdout:
                f.write(line)
                f.flush()
            code = proc.wait()
            f.write(f"\n[exit] code={code} finished_at={_now()}\n")

    threading.Thread(target=_tee, daemon=True).start()
    return rid


def _run_status(rid: str) -> dict:
    if rid in _runs:
        proc = _runs[rid]["proc"]
        return {"id": rid, "mode": _runs[rid]["mode"], "started": _runs[rid]["started"],
                "running": proc.poll() is None, "code": proc.poll()}
    rdir = RUNS_DIR / rid
    logf = rdir / "log.txt"
    if not logf.exists():
        raise HTTPException(404, "run not found")
    text = logf.read_text(encoding="utf-8", errors="replace")
    code = None
    if "[exit] code=" in text:
        code = int(text.split("[exit] code=")[1].split()[0])
    return {"id": rid, "mode": "quiet", "started": "", "running": code is None, "code": code}


# ---------------------------------------------------------------- Endpoints
@app.get("/api/health")
def health():
    cfg = None
    try:
        cfg = load_config()
    except Exception:
        pass
    return {
        "ok": True,
        "time_utc": _now(),
        "config_file": CONFIG_PATH.exists(),
        "state_file": STATE_PATH.exists(),
        "scenarios_file": SCENARIOS_PATH.exists(),
        "token": bool((os.environ.get("IG_ACCESS_TOKEN") or "").strip()),
        "ig_user_id": bool((os.environ.get("IG_USER_ID") or "").strip()),
        "ffmpeg": bool(os.system("ffmpeg -version >nul 2>nul") == 0) if os.name == "nt" else None,
    }


@app.get("/api/overview")
def overview():
    state = load_state()
    cfg = load_config()
    epi = state.get("last_episode") or {}
    videos = sorted(OUT_DIR.glob("reel_*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    latest = videos[0] if videos else None
    arc = engine.load_scenarios().get("arcs", {}).get(state.get("arc", ""), {})
    node = (arc.get("nodes") or {}).get(state.get("node", ""), {})
    return {
        "channel": cfg.get("handle", "@you"),
        "handle": cfg.get("handle", "@you"),
        "season": state.get("season", 1),
        "day": state.get("day", 0),
        "arc_title": arc.get("title", state.get("arc", "")),
        "location": state.get("location", ""),
        "stats": state.get("stats", {}),
        "stats_labels": cfg.get("stats_labels", {}),
        "posted": len(state.get("history", [])),
        "awaiting_arc": bool(state.get("awaiting_arc")),
        "last_episode": {
            "day": epi.get("day"), "vote": epi.get("vote"),
            "votes": epi.get("votes"), "closed": epi.get("closed"),
            "post_url": epi.get("post_url"), "media_id": epi.get("media_id"),
        } if epi else None,
        "latest_video": {"name": latest.name, "mtime": latest.stat().st_mtime,
                         "seconds": latest.stat().st_size / 1e6} if latest else None,
        "next_node": {
            "id": state.get("node", ""), "place": node.get("place", ""),
            "choices": [c.get("label", c.get("next")) for c in (node.get("choices") or [])],
        },
        "publish_hour": cfg.get("publish_after_ist_hour", 13),
        "token": bool((os.environ.get("IG_ACCESS_TOKEN") or "").strip()),
    }


@app.get("/api/state")
def api_state():
    return JSONResponse(load_state())


@app.get("/api/story")
def api_story():
    state = load_state()
    scn = engine.load_scenarios()
    arc = scn.get("arcs", {}).get(state.get("arc", ""), {})
    nodes = []
    for nid, nd in (arc.get("nodes") or {}).items():
        nodes.append({
            "id": nid, "day": nd.get("day"), "place": nd.get("place", ""),
            "scene": nd.get("scene", ""), "vote": bool(nd.get("choices")),
            "choices": [{"label": c.get("label"), "next": c.get("next")}
                        for c in (nd.get("choices") or [])],
        })
    arcs = [{"id": k, "title": v.get("title", k),
             "nodes": len(v.get("nodes") or {})} for k, v in scn.get("arcs", {}).items()]
    return {"current_arc": state.get("arc", ""), "node": state.get("node", ""),
            "season": state.get("season", 1), "day": state.get("day", 0),
            "nodes": nodes, "arcs": arcs}


@app.get("/api/scenarios")
def api_scenarios_raw():
    return JSONResponse(load_json(SCENARIOS_PATH) or {})


@app.put("/api/scenarios")
async def put_scenarios(req: Request):
    try:
        body = await req.json()
    except Exception:
        raise HTTPException(400, "invalid JSON")
    if not isinstance(body, dict) or "arcs" not in body:
        raise HTTPException(400, "scenarios.json must be an object with 'arcs'")
    tmp = SCENARIOS_PATH.with_suffix(".tmp")
    tmp.write_text(json_dumps(body), encoding="utf-8")
    tmp.replace(SCENARIOS_PATH)
    return {"ok": True, "nodes": sum(len(a.get("nodes") or {})
                                    for a in body.get("arcs", {}).values())}


def json_dumps(o) -> str:
    import json
    return json.dumps(o, ensure_ascii=False, indent=2) + "\n"


@app.get("/api/config")
def api_config(redact: bool = True):
    cfg = load_json(CONFIG_PATH) or load_json(EXAMPLE_CONFIG_PATH) or {}
    cfg = dict(cfg)
    for k in ("ig_access_token", "ig_user_id", "access_token"):
        if redact and k in cfg and cfg[k]:
            cfg[k] = "***set***"
    return cfg


@app.put("/api/config")
async def put_config(req: Request):
    try:
        body = await req.json()
    except Exception:
        raise HTTPException(400, "invalid JSON")
    cur = load_json(CONFIG_PATH) or load_json(EXAMPLE_CONFIG_PATH) or {}
    for k, v in body.items():
        if v == "***set***":
            continue
        cur[k] = v
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json_dumps(cur), encoding="utf-8")
    tmp.replace(CONFIG_PATH)
    return {"ok": True}


@app.get("/api/episodes")
def api_episodes():
    state = load_state()
    vids = []
    for p in sorted(OUT_DIR.glob("reel_*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True):
        vids.append({"name": p.name, "bytes": p.stat().st_size,
                     "mtime": p.stat().st_mtime, "url": f"/api/video/{p.name}"})
    stills = [p.name for p in sorted((OUT_DIR / "stills").glob("*.png"))[:24]] \
        if (OUT_DIR / "stills").is_dir() else []
    return {"videos": vids, "stills": stills, "history": state.get("history", [])[-12:]}


@app.get("/api/video/{name}")
def api_video(name: str):
    p = OUT_DIR / _safe_name(name)
    if p.suffix != ".mp4" or not p.exists():
        raise HTTPException(404, "video not found")
    return FileResponse(p, media_type="video/mp4")


@app.get("/api/still/{name}")
def api_still(name: str):
    p = OUT_DIR / "stills" / _safe_name(name)
    if p.suffix != ".png" or not p.exists():
        raise HTTPException(404, "not found")
    return FileResponse(p, media_type="image/png")


@app.post("/api/trigger")
async def trigger(mode: str = "dry"):
    if mode not in ("dry", "stills", "full"):
        raise HTTPException(400, "mode must be dry|stills|full")
    if mode == "full" and not (os.environ.get("IG_ACCESS_TOKEN") or "").strip():
        # full run without token = publish fail tail pe, but render takes time — allow anyway? No.
        return {"ok": False, "error": "IG_ACCESS_TOKEN not set — 'full' publish mode unavailable. "
                                      "Use dry/stills. Full post karne ke liye secrets set karo."}
    rid = _start_run(mode)
    return {"ok": True, "id": rid}


@app.get("/api/runs")
def api_runs():
    ids = sorted((p for p in RUNS_DIR.iterdir() if p.is_dir()),
                 key=lambda p: p.name, reverse=True)[:20]
    items = []
    for p in ids:
        try:
            s = _run_status(p.name)
        except HTTPException:
            continue
        items.append(s)
    return {"runs": items}


@app.get("/api/runs/{rid}/log")
def api_run_log(rid: str):
    logf = RUNS_DIR / Path(rid).name / "log.txt"
    if not logf.exists():
        raise HTTPException(404, "run not found")
    try:
        since = int(float(logf.stat().st_mtime * 1000))
    except Exception:
        since = 0
    return {"log": logf.read_text(encoding="utf-8", errors="replace")[-128000:], "mtime": since}


@app.get("/api/chart/stats")
def api_chart():
    """History se stats ka journey — gauges ke liye."""
    state = load_state()
    return {"stats": state.get("stats", {}), "day": state.get("day"),
            "history": state.get("history", [])[-15:]}


# Static SPA
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    print("[zmb-dashboard] http://127.0.0.1:8787")
    uvicorn.run(app, host="127.0.0.1", port=8787, log_level="warning")
