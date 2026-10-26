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
    params = {
        "model": model,
        "duration": seconds,
        "aspectRatio": "9:16",
        "seed": seed,
    }
    response = requests.get(
        VIDEO_ENDPOINT + quote(prompt, safe=""),
        params=params,
        headers={"Authorization": "Bearer " + key, "Accept": "video/mp4,application/json"},
        timeout=(30, 600),
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"video provider HTTP {response.status_code}; check video permission, selected model and credits"
        )
    video_bytes = _extract_video_bytes(response)
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(".tmp.mp4")
    tmp.write_bytes(video_bytes)
    tmp.replace(output)
    duration = _probe_duration(output)
    if output.stat().st_size < 100_000 or duration <= 0:
        output.unlink(missing_ok=True)
        raise RuntimeError("video provider response failed MP4 validation")
    Log(f"[ai-video] source clip ready: {output.name}, {duration:.1f}s")
    return duration


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


def render_ai_video(cfg: dict, episode: dict, voices: list[dict], shots: list,
                    total: float, audio_path: Path, work: Path, out_path: Path,
                    fps: int, out_w: int, out_h: int, crf: int, Log=log) -> dict:
    key = (os.environ.get("POLLINATIONS_KEY") or "").strip()
    if not key:
        raise RuntimeError("POLLINATIONS_KEY with video-generation permission is required for ai_video mode")
    model = str(cfg.get("ai_video_model") or "google/veo-3.1-fast")
    seconds = max(4, min(8, int(cfg.get("ai_video_clip_seconds", 6))))
    base = work / "ai_video"
    source_dir, overlay_dir, clip_dir = base / "source", base / "overlays", base / "clips"
    source_dir.mkdir(parents=True, exist_ok=True)
    overlay_dir.mkdir(parents=True, exist_ok=True)
    clip_dir.mkdir(parents=True, exist_ok=True)
    source_clips: list[Path] = []
    source_durations: list[float] = []
    lines = episode.get("lines") or []
    started = time.time()

    # One moving clip per narrated beat. Prompt hashes make retries reuse any clip
    # already generated during the same runner workspace.
    for index, line in enumerate(lines):
        prompt = build_video_prompt(episode, line, seconds)
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        path = source_dir / f"{index:02d}_{digest[:12]}.mp4"
        duration = _probe_duration(path) if path.exists() and path.stat().st_size > 100_000 else 0.0
        if duration <= 0:
            failure = None
            for attempt in range(3):
                try:
                    Log(f"[ai-video] generating moving scene {index + 1}/{len(lines)} with model={model}")
                    duration = generate_video(
                        prompt, key, model, seconds, path, int(digest[:8], 16) & 0x7FFFFFFF, Log
                    )
                    failure = None
                    break
                except Exception as exc:
                    failure = exc
                    Log(f"[ai-video] scene {index + 1} attempt {attempt + 1}/3 failed: {type(exc).__name__}")
                    if attempt < 2:
                        time.sleep(3 + 5 * attempt)
            if failure is not None:
                raise RuntimeError(
                    f"AI video generation failed on scene {index + 1}; check POLLINATIONS_KEY, "
                    "video model availability and remaining credits"
                ) from failure
        source_clips.append(path)
        source_durations.append(duration)

    line_index = 0
    segments: list[Path] = []
    for index, shot in enumerate(shots):
        if shot.kind == "title":
            source_index, overlay_kind, text = 0, "title", ""
        elif shot.kind == "line":
            source_index = min(line_index, len(source_clips) - 1)
            overlay_kind = "line"
            text = voices[min(line_index, len(voices) - 1)].get("text", shot.text or "")
            line_index += 1
        elif shot.kind == "vote":
            source_index, overlay_kind, text = len(source_clips) - 1, "vote", episode.get("subtitle", "")
        elif shot.kind == "ending":
            source_index, overlay_kind, text = len(source_clips) - 1, "ending", episode.get("subtitle", "")
        else:
            source_index, overlay_kind, text = len(source_clips) - 1, "line", str(shot.text or "")
        overlay = _overlay(
            overlay_dir / f"overlay_{index:02d}.png", episode, overlay_kind, text, out_w, out_h
        )
        segment = clip_dir / f"segment_{index:02d}.mp4"
        _render_segment(
            source_clips[source_index], overlay, source_durations[source_index],
            float(shot.dur), segment, fps, out_w, out_h, crf, Log,
        )
        segments.append(segment)

    concat = base / "concat.txt"
    concat.write_text(
        "".join(f"file '{p.resolve().as_posix()}'\n" for p in segments), encoding="utf-8"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(concat),
        "-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "160k", "-ac", "2", "-ar", "44100",
        "-shortest", "-t", f"{total:.3f}", str(out_path),
    ])
    actual = _probe_duration(out_path)
    if not out_path.exists() or out_path.stat().st_size < 100_000 or actual <= 0:
        raise RuntimeError("AI video Reel failed output validation")
    result = {
        "video_path": str(out_path),
        "duration": actual,
        "frames": int(round(actual * fps)),
        "shots": len(shots),
        "render_seconds": round(time.time() - started, 1),
        "visual_mode_used": "ai_video",
    }
    Log(f"[render] AI VIDEO DONE {out_path.name} {actual:.1f}s {out_path.stat().st_size / 1e6:.2f} MB")
    return result
