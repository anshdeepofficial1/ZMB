"""Render pipeline: images -> TTS -> FFmpeg -> vertical 9:16 reel.

Flow:
  1. Har narration chunk / image prompt ke liye image (Pollinations → Pixabay → placeholder)
  2. Puri narration ki edge-tts voice + subtitles (SRT)
  3. Har image ka slow zoom clip (zoompan), phir concat
  4. Final pass: subtitles burn + day-title + stats HUD + choice text + music mix
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
import shutil
import sys
import textwrap
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import ASSETS_DIR, OUT_DIR, log, run  # noqa: E402

import requests  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

FONT_CANDIDATES = [
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("C:/Windows/Fonts/arialbd.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]


def pick_font_path() -> Path | None:
    for p in FONT_CANDIDATES:
        if p.exists():
            return p
    return None


def seed_for(episode: dict, index: int) -> int:
    raw = f"{episode['season']}-{episode['day']}-{index}"
    return int(hashlib.md5(raw.encode()).hexdigest()[:8], 16) % 1_000_000


# ---------------------------------------------------------------- images ----

def fetch_pollinations(cfg: dict, prompt: str, seed: int, out_path: Path) -> bool:
    key = (os.environ.get("POLLINATIONS_KEY") or "").strip()
    quoted = urllib.parse.quote(prompt, safe="")
    delay = int(cfg.get("image_delay_seconds", 45))

    if key:
        # gen.pollinations.ai — better models, no per-IP limit (free key)
        url = f"https://gen.pollinations.ai/image/{quoted}"
        params = {
            "model": cfg.get("pollinations_model", "flux"),
            "width": 1080, "height": 1920, "seed": seed,
        }
        headers = {"Authorization": f"Bearer {key}"}
        attempts = [(url, params, headers)]
    else:
        # classic anonymous tier — 1 image per ~45s, 768px max area
        url = f"https://image.pollinations.ai/prompt/{quoted}"
        params = {
            "model": cfg.get("pollinations_model", "flux"),
            "width": int(cfg.get("image_width", 576)),
            "height": int(cfg.get("image_height", 1024)),
            "seed": seed, "nologo": "true",
        }
        attempts = [(url, params, {})]

    for url, params, headers in attempts:
        for attempt in range(4):
            try:
                r = requests.get(url, params=params, headers=headers, timeout=180)
            except requests.RequestException as exc:
                log(f"[render] pollinations network error: {exc}")
                time.sleep(10)
                continue
            if r.status_code == 200 and len(r.content) > 5000:
                out_path.write_bytes(r.content)
                return True
            if r.status_code == 402:
                wait = min(int(r.headers.get("Retry-After", delay) or delay), 120)
                log(f"[render] pollinations rate-limited (402), waiting {wait}s")
                time.sleep(wait)
                continue
            log(f"[render] pollinations HTTP {r.status_code} (attempt {attempt + 1})")
            time.sleep(5 + attempt * 5)
    return False


def fetch_pixabay(cfg: dict, index: int, out_path: Path) -> bool:
    key = (os.environ.get("PIXABAY_API_KEY") or "").strip()
    if not key:
        return False
    queries = cfg.get("pixabay_queries") or ["dark fog road"]
    query = queries[index % len(queries)]
    try:
        r = requests.get(
            "https://pixabay.com/api/",
            params={
                "key": key, "q": query, "image_type": "photo",
                "orientation": "vertical", "safesearch": "true", "per_page": 20,
            },
            timeout=60,
        )
        hits = r.json().get("hits", [])
        if not hits:
            return False
        pick = random.choice(hits[:10])
        img_url = pick.get("largeImageURL") or pick.get("webformatURL")
        data = requests.get(img_url, timeout=120).content
        if len(data) > 5000:
            out_path.write_bytes(data)
            return True
    except Exception as exc:
        log(f"[render] pixabay failed: {exc}")
    return False


def make_placeholder(prompt: str, out_path: Path) -> None:
    img = Image.new("RGB", (1080, 1920), (12, 14, 18))
    draw = ImageDraw.Draw(img)
    font = None
    fp = pick_font_path()
    if fp:
        try:
            font = ImageFont.truetype(str(fp), 44)
        except Exception:
            font = None
    wrapped = "\n".join(textwrap.wrap(prompt[:280], width=40))
    draw.multiline_text((70, 700), wrapped, fill=(190, 190, 190), font=font, spacing=14)
    img.save(out_path, quality=88)


def build_images(cfg: dict, episode: dict, work: Path) -> list[Path]:
    provider = cfg.get("image_provider", "pollinations")
    anonymous_pollinations = provider == "pollinations" and not (os.environ.get("POLLINATIONS_KEY") or "").strip()
    images: list[Path] = []

    for i, prompt in enumerate(episode["images"]):
        out = work / f"img_{i:02d}.jpg"
        ok = False
        if provider == "pollinations":
            ok = fetch_pollinations(cfg, prompt, seed_for(episode, i), out)
            if not ok:
                ok = fetch_pixabay(cfg, i, out)
        else:
            ok = fetch_pixabay(cfg, i, out)
            if not ok:
                ok = fetch_pollinations(cfg, prompt, seed_for(episode, i), out)
        if not ok:
            log(f"[render] image {i}: placeholder use ho raha hai")
            make_placeholder(prompt, out)
        images.append(out)
        if anonymous_pollinations and i < len(episode["images"]) - 1:
            time.sleep(int(cfg.get("image_delay_seconds", 45)))
    return images


# ------------------------------------------------------------------- tts ----

def build_voice(cfg: dict, narration: list[str], work: Path) -> tuple[Path, Path]:
    """edge-tts ki Python API se voice + subtitles. (CLI/PATH pe depend nahi karta.)"""
    import asyncio

    import edge_tts

    text = "\n".join(narration)
    mp3 = work / "voice.mp3"
    srt = work / "voice.srt"
    voice = cfg.get("voice", "en-IN-PrabhatNeural")
    rate = str(cfg.get("voice_rate", "-6%"))

    async def synth() -> None:
        tts = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
        submaker = edge_tts.SubMaker()
        with open(mp3, "wb") as audio:
            async for chunk in tts.stream():
                if chunk["type"] == "audio":
                    audio.write(chunk["data"])
                elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                    submaker.feed(chunk)
        srt.write_text(submaker.get_srt(), encoding="utf-8")

    last_error = None
    for attempt in range(3):
        try:
            asyncio.run(synth())
            if mp3.exists() and mp3.stat().st_size > 2000:
                merge_srt(srt)
                return mp3, srt
        except Exception as exc:
            last_error = exc
            log(f"[render] edge-tts attempt {attempt + 1} failed: {exc}")
        time.sleep(5)
    raise RuntimeError(f"edge-tts failed after retries: {last_error}")


_TS = re.compile(r"(\d\d:\d\d:\d\d,\d\d\d) --> (\d\d:\d\d:\d\d,\d\d\d)")


def merge_srt(srt_path: Path, max_words: int = 3, max_chars: int = 22) -> None:
    """Word-level cues ko 3-3 words ke bold chunks mein merge karo (reels style)."""
    if not srt_path.exists() or srt_path.stat().st_size == 0:
        return
    blocks = [b for b in re.split(r"\n\s*\n", srt_path.read_text(encoding="utf-8")) if b.strip()]
    cues: list[tuple[str, str, str]] = []
    for block in blocks:
        m = _TS.search(block)
        if not m:
            continue
        word = " ".join(
            line.strip() for line in block.splitlines()
            if not _TS.search(line) and not line.strip().isdigit()
        ).strip()
        if word:
            cues.append((m.group(1), m.group(2), word))

    merged: list[tuple[str, str, str]] = []
    group: list[tuple[str, str, str]] = []
    for cue in cues:
        candidate = group + [cue]
        joined = " ".join(c[2] for c in candidate)
        if group and (len(candidate) > max_words or len(joined) > max_chars):
            merged.append((group[0][0], group[-1][1], " ".join(c[2] for c in group)))
            group = [cue]
        else:
            group = candidate
    if group:
        merged.append((group[0][0], group[-1][1], " ".join(c[2] for c in group)))

    out = "\n".join(f"{i}\n{s} --> {e}\n{t}\n" for i, (s, e, t) in enumerate(merged, start=1))
    srt_path.write_text(out, encoding="utf-8")


def probe_duration(path: Path) -> float:
    res = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", str(path)])
    return float(res.stdout.strip())


# ----------------------------------------------------------------- clips ----

def build_clips(cfg: dict, images: list[Path], weights: list[float], voice_dur: float, work: Path):
    fps = int(cfg.get("fps", 30))
    n = len(images)
    total_w = sum(weights) or n
    durations = [max(2.2, voice_dur * (weights[i] / total_w)) for i in range(n)]
    scale = voice_dur / sum(durations)
    durations = [d * scale for d in durations]
    durations[-1] = max(2.0, voice_dur - sum(durations[:-1]))
    durations = [round(d, 2) for d in durations]

    clips: list[Path] = []
    for i, (img, dur) in enumerate(zip(images, durations)):
        clip = work / f"clip_{i:02d}.mp4"
        zoom = "min(1+0.0012*on,1.18)" if i % 2 == 0 else "max(1.18-0.0012*on,1.0)"
        vf = (
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d=1:s=1080x1920:fps={fps}"
        )
        run([
            "ffmpeg", "-y", "-loop", "1", "-framerate", str(fps), "-t", str(dur), "-i", str(img),
            "-vf", vf, "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-pix_fmt", "yuv420p", "-an", str(clip),
        ])
        clips.append(clip)
    return clips, durations


def concat_clips(clips: list[Path], work: Path) -> Path:
    listfile = work / "concat.txt"
    listfile.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    silent = work / "silent.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(silent)], cwd=work)
    return silent


# ---------------------------------------------------------------- compose ----

def wrap_text(text: str, width: int = 34) -> str:
    return "\n".join(textwrap.wrap(text, width=width)) or text


def write_textfile(work: Path, name: str, text: str) -> None:
    (work / name).write_text(text, encoding="utf-8")


def pick_music() -> Path | None:
    music_dir = ASSETS_DIR / "music"
    if not music_dir.exists():
        return None
    tracks = sorted(music_dir.glob("*.mp3"))
    return random.choice(tracks) if tracks else None


def compose_final(cfg: dict, episode: dict, work: Path, silent: Path, voice: Path,
                  srt: Path, total: float, out_path: Path) -> None:
    fps = int(cfg.get("fps", 30))
    stats = episode.get("stats", {})

    title = f"SEASON {episode['season']} \u00b7 DIN {episode['day']}\n{episode['subtitle']}"
    hud = f"HP {stats.get('hp', '--')} \u00b7 NOISE {stats.get('noise', '--')} \u00b7 SUPPLIES {stats.get('supplies', '--')}"
    write_textfile(work, "title.txt", title)
    write_textfile(work, "hud.txt", hud)

    filters = []
    if srt.exists() and srt.stat().st_size > 0:
        filters.append(
            "subtitles=voice.srt:force_style="
            "'Fontname=DejaVu Sans,FontSize=13,Bold=1,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00101010,BorderStyle=1,Outline=3,Shadow=0,MarginV=210,Alignment=2'"
        )

    # drawtext: ffmpeg 9 on Windows crashes without an explicit fontfile
    # (broken fontconfig). Copy a real ttf into work/ and reference it
    # relative to cwd, so this works identically on Windows + Ubuntu CI.
    font = pick_font_path()
    font_arg = ""
    if font:
        shutil.copy2(font, work / "font_bold.ttf")
        font_arg = "fontfile=font_bold.ttf:"

    filters += [
        f"drawtext={font_arg}textfile=title.txt:fontcolor=white:fontsize=40:line_spacing=10:"
        "box=1:boxcolor=black@0.55:boxborderw=16:x=(w-text_w)/2:y=70",
        f"drawtext={font_arg}textfile=hud.txt:fontcolor=white:fontsize=30:"
        "box=1:boxcolor=black@0.45:boxborderw=12:x=60:y=300",
    ]

    if episode.get("vote") and episode.get("choices"):
        lines = "\n".join(
            wrap_text(f"{i}. {c['text']}", 30) for i, c in enumerate(episode["choices"], start=1)
        )
        write_textfile(work, "choices.txt", lines)
        t0 = max(4.0, total * 0.6)
        filters.append(
            f"drawtext={font_arg}textfile=choices.txt:fontcolor=white:fontsize=48:line_spacing=16:"
            "box=1:boxcolor=black@0.65:boxborderw=20:x=(w-text_w)/2:y=h-660:"
            f"enable='gte(t,{t0:.1f})'"
        )

    fc = f"[0:v]{','.join(filters)}[outv]"
    music = pick_music()
    cmd = ["ffmpeg", "-y", "-i", "silent.mp4", "-i", "voice.mp3"]
    if music:
        shutil.copy2(music, work / "music.mp3")
        cmd += ["-stream_loop", "-1", "-i", "music.mp3"]
        fc += (
            ";[1:a]volume=1.0[voice];"
            f"[2:a]volume={cfg.get('music_volume', 0.12)}[music];"
            "[voice][music]amix=inputs=2:duration=first:normalize=0[outa]"
        )
    else:
        fc += ";[1:a]volume=1.0[outa]"

    cmd += [
        "-filter_complex", fc,
        "-map", "[outv]", "-map", "[outa]",
        "-r", str(fps), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart", "-t", str(total),
        str(out_path),
    ]
    run(cmd, cwd=work)


# ------------------------------------------------------------------ main ----

def render_episode(cfg: dict, episode: dict) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    work = OUT_DIR / f"work_s{episode['season']}_d{episode['day']:03d}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    log(f"[render] episode S{episode['season']} D{episode['day']} — images ({cfg.get('image_provider')})")
    images = build_images(cfg, episode, work)

    log("[render] voice (edge-tts)")
    voice, srt = build_voice(cfg, episode["narration"], work)
    total = probe_duration(voice)
    max_seconds = float(cfg.get("max_duration_seconds", 60))
    if total > max_seconds:
        log(f"[render] voice {total:.1f}s > max {max_seconds}s — cut kiya ja raha hai")
        total = max_seconds

    narr = episode["narration"]
    n_img = len(images)
    weights = [0.0] * n_img
    for j, line in enumerate(narr):
        weights[j % n_img] += max(8, len(line.split()))
    if sum(weights) <= 0:
        weights = [1.0] * n_img

    log("[render] clips + concat")
    clips, durations = build_clips(cfg, images, weights, total, work)
    silent = concat_clips(clips, work)

    out_path = OUT_DIR / episode["video_name"]
    log(f"[render] final compose → {out_path.name}")
    compose_final(cfg, episode, work, silent, voice, srt, total, out_path)

    (OUT_DIR / "caption.txt").write_text(episode["caption"], encoding="utf-8")
    (OUT_DIR / "episode.json").write_text(
        json.dumps(episode, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(f"[render] done ({sum(durations):.1f}s clips, voice {total:.1f}s)")
    return {"video_path": str(out_path), "duration": total}
