"""Optional true AI-motion video renderer for ZMB.

Uses Pollinations' video endpoint (model default: Google Veo 3.1 Fast) to generate a short moving
clip per narration beat. This may consume paid provider credits. It is deliberately
opt-in; ai_storyboard remains the default budget-conscious visual mode.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
import time
from pathlib import Path
from urllib.parse import quote

import requests
from ai_storyboard import build_prompt, _overlay
from common import log, run

VIDEO_ENDPOINT = "https://gen.pollinations.ai/video/"


def build_video_prompt(episode: dict, line: dict, duration: int) -> str:
    shot = line.get("shot") or {}
    cast = shot.get("cast") or []
    cast_moves = []
    for item in cast:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            who, action = str(item[0]), str(item[1]).replace("_", " ")
            cast_moves.append(f"{who}: {action}")
    move_text = "; ".join(cast_moves) if cast_moves else "natural movement by the visible survivor characters"
    camera = str(shot.get("cam") or "cinematic slow push").replace("_", " ")
    base = build_prompt(episode, line)
    return (
        base
        + f" This is an actual moving video clip lasting about {duration} seconds, not a still image. "
        + f"Continuous visible movement: {move_text}. "
        + "Animate natural body movement, walking or running when specified, breathing, blinking, "
        + "subtle head turns, dog movement and drifting environmental atmosphere. "
        + f"Camera direction: {camera}; use smooth film-like camera motion that supports the action. "
        + "Keep character appearances and clothing consistent throughout this clip. One single shot, a single continuous take, "
        + "no hard cuts, no montage, no freeze frame, no zoom-only still-image effect, no text, no logo."
    )


def _extract_video_bytes(response: requests.Response) -> bytes:
    content_type = str(response.headers.get("Content-Type", "")).lower()
    body = response.content
    # The endpoint can return an MP4 directly or a JSON media envelope.
    if "json" in content_type or body[:1] in (b"{", b"["):
        try:
            payload = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("video provider returned malformed JSON") from exc
        rows = payload.get("data") if isinstance(payload, dict) else None
        item = rows[0] if isinstance(rows, list) and rows else (payload if isinstance(payload, dict) else {})
        if isinstance(item, dict) and item.get("b64_json"):
            return base64.b64decode(item["b64_json"])
        video_url = item.get("url") if isinstance(item, dict) else None
        if video_url:
            fetched = requests.get(video_url, timeout=(20, 300))
            if fetched.status_code >= 400:
                raise RuntimeError(f"video file download failed with HTTP {fetched.status_code}")
            return fetched.content
        raise RuntimeError("video provider response did not include video bytes or a URL")
    if len(body) > 100_000 and (content_type.startswith("video/") or body[4:8] == b"ftyp" or "octet-stream" in content_type):
        return body
    # Some gateways return binary MP4 without a precise Content-Type.
    if len(body) > 100_000 and body[4:8] == b"ftyp":
        return body
    raise RuntimeError("video provider did not return an MP4 file")


def _probe_duration(path: Path) -> float:
    result = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path),
    ])
    try:
        return float((result.stdout or "0").strip())
    except ValueError:
        return 0.0


def generate_video(prompt: str, key: str, model: str, seconds: int,
                   output: Path, seed: int, Log=log) -> float:
    """Legacy hosted video generation is intentionally blocked."""
    raise RuntimeError("Hosted video inference is disabled; use the existing local procedural renderer")


def _render_segment(source: Path, overlay: Path, source_duration: float,
                    target_duration: float, output: Path, fps: int,
                    width: int, height: int, crf: int, Log=log) -> None:
    # Retime the generated shot to the narration timeline, then apply a fixed,
    # readable title/subtitle layer; the underlying footage remains genuinely moving.
    speed = max(0.25, min(4.0, target_duration / max(0.1, source_duration)))
    graph = (
        f"[0:v]setpts=PTS*{speed:.6f},"
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,fps={fps},"
        f"tpad=stop_mode=clone:stop_duration={target_duration:.3f},"
        f"trim=duration={target_duration:.3f},setpts=PTS-STARTPTS[bg];"
        f"[1:v]scale={width}:{height},format=rgba[ol];"
        f"[bg][ol]overlay=0:0:shortest=1,format=yuv420p[v]"
    )
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(source),
        "-loop", "1", "-framerate", str(fps), "-i", str(overlay),
        "-filter_complex", graph, "-map", "[v]", "-an",
        "-t", f"{target_duration:.3f}", "-r", str(fps),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
    ])
    Log(f"[ai-video] rendered moving segment {output.name}")


def render_ai_video(*args, **kwargs) -> dict:
    """Legacy hosted video entry point retained but network calls are disabled."""
    raise RuntimeError("Hosted video inference is disabled in ZMB local-only mode")
