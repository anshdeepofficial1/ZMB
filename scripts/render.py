"""Episode renderer: English narration (edge-tts) -> timeline -> cartoon frames -> MP4.

Flow:
  1. Har narration line ka TTS (word timings ke saath) → padded WAV
  2. Timeline: 1 line = 1 shot (place/action/camera), plus title/vote/ending cards
  3. Frames: SVG compose (animate.py) → PNG (resvg, multi-process)
  4. FFmpeg: frames + master audio → 1080x1920 H.264/AAC reel

Local:
  python scripts/render.py --dry-run        # current state se ek episode render karo
  python scripts/render.py --stills out/x   # sirf ek-ek still per line (fast check)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import animate as an  # noqa: E402
import characters as ch  # noqa: E402
import engine  # noqa: E402
import scenes as sc  # noqa: E402
import svgrender  # noqa: E402
from common import OUT_DIR, ROOT, WORK_DIR, load_config, load_state, log, run  # noqa: E402


# ------------------------------------------------------------------- voice ---

def _probe_dur(path) -> float:
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)])
    try:
        return float((r.stdout or "0").strip())
    except ValueError:
        return 0.0


async def _tts_line(text, voice, rate, out_mp3: Path):
    import edge_tts

    comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    audio = bytearray()
    words: list[dict] = []
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
        elif chunk["type"] == "WordBoundary":
            start = float(chunk["offset"]) / 1e7
            end = (float(chunk["offset"]) + float(chunk["duration"])) / 1e7
            words.append({"w": str(chunk["text"]).strip(), "start": start, "end": end})
    if not audio:
        raise RuntimeError("edge-tts returned no audio")
    out_mp3.write_bytes(bytes(audio))
    return [w for w in words if w["w"]]


def _estimate_words(text: str, dur: float) -> list[dict]:
    """TTS fail hone par evenly distributed fallback timings."""
    ws = [w for w in text.split() if w]
    if not ws:
        return []
    total = sum(len(w) + 1 for w in ws)
    out, cur = [], 0.12
    span = max(0.6, dur - 0.35)
    for w in ws:
        d = span * (len(w) + 1) / total
        out.append({"w": w, "start": round(cur, 3), "end": round(cur + d, 3)})
        cur += d
    return out


def synthesize_voices(cfg: dict, ep: dict, work: Path, Log=log) -> list[dict]:
    voice = cfg.get("voice", "en-US-ChristopherNeural")
    rate = cfg.get("voice_rate", "-4%")
    gap = float(cfg.get("render", cfg).get("gap_seconds", 0.45))
    a_dir = work / "audio"
    a_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for i, line in enumerate(ep["lines"]):
        text = line["text"]
        mp3 = a_dir / f"l{i:02d}.mp3"
        wav = a_dir / f"l{i:02d}.wav"
        words: list[dict] = []
        got = False
        for attempt in range(3):
            try:
                words = asyncio.run(_tts_line(text, voice, rate, mp3))
                got = True
                break
            except Exception as exc:  # noqa: BLE001
                Log(f"    tts retry {attempt + 1} for line {i}: {exc}")
                time.sleep(1.2 + attempt)
        if not got:
            Log(f"    tts FAILED line {i} — silent fallback")
            run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                 "-i", f"anullsrc=r=24000:cl=mono", "-t", "3.0", "-c:a", "pcm_s16le", str(mp3)])
        raw = _probe_dur(mp3)
        run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(mp3),
             "-af", f"apad=pad_dur={gap}", "-ar", "24000", "-ac", "1",
             "-c:a", "pcm_s16le", str(wav)])
        dur = _probe_dur(wav)
        if not words:
            words = _estimate_words(text, dur)
        out.append({"text": text, "shot": line.get("shot", {}), "words": words,
                    "dur": dur, "wav": wav, "raw": raw})
    return out


def _silence(seconds: float, path: Path) -> Path:
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
         "-i", "anullsrc=r=24000:cl=mono", "-t", f"{max(0.02, seconds):.3f}",
         "-c:a", "pcm_s16le", str(path)])
    return path


def build_master_audio(voices, lead, outro, work: Path, total=None, cfg=None) -> Path:
    a_dir = work / "audio"
    parts: list[Path] = []
    if lead > 0.02:
        parts.append(_silence(lead, a_dir / "lead.wav"))
    parts += [v["wav"] for v in voices]
    if outro > 0.02:
        parts.append(_silence(outro, a_dir / "outro.wav"))
    if not parts:
        parts = [_silence(3.0, a_dir / "empty.wav")]
    lst = a_dir / "concat.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    master = a_dir / "master.wav"
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(master)])

    # optional music bed (assets/music/*.mp3) — low volume neeche narration ke
    cfg = cfg or {}
    vol = float(cfg.get("music_volume", 0.0) or 0.0)
    music_dir = ROOT / "assets" / "music"
    tracks = sorted(music_dir.glob("*.mp3")) if music_dir.exists() else []
    if not tracks or vol <= 0.001 or not total:
        return master
    track = tracks[abs(hash(work.name)) % len(tracks)]
    mixed = a_dir / "mixed.wav"
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(master),
         "-stream_loop", "-1", "-i", str(track), "-filter_complex",
         f"[1:a]volume={vol:.3f},atrim=0:{total:.3f},afade=t=out:st={max(0.0, total - 2.0):.2f}:d=2[m];"
         f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]",
         "-map", "[a]", "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(mixed)])
    return mixed


# ------------------------------------------------------------------ render ---

def render_episode(cfg: dict, ep: dict, *, jobs=None, scale=None, crf=None,
                   keep_frames=False, Log=log) -> dict:
    r = dict(cfg.get("render", cfg))
    fps = int(r.get("fps", 30))
    iw = int(r.get("width", 810))
    ih = int(r.get("height", 1440))
    ow = int(r.get("out_width", 1080))
    oh = int(r.get("out_height", 1920))
    jobs = int(jobs or r.get("jobs", 4) or 4)
    crf = int(crf if crf is not None else r.get("crf", 20))
    if scale:
        iw, ih = int(ow * scale), int(oh * scale)
        if iw % 2:
            iw += 1
        if ih % 2:
            ih += 1

    tag = f"s{ep['season']}_d{ep['day']:03d}"
    work = WORK_DIR / f"render_{tag}"
    work.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / ep.get("video_name", f"reel_{tag}.mp4")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    Log(f"[render] voice: {len(ep['lines'])} lines (voice={cfg.get('voice')})")
    voices = synthesize_voices(cfg, ep, work, Log)
    shots, total, lead = an.build_timeline(ep, cfg, voices)
    outro = max(0.0, total - lead - sum(v["dur"] for v in voices))
    Log(f"[render] timeline: {len(shots)} shots, {total:.1f}s "
        f"({len(shots) + 1} cards incl.), fps={fps}, {iw}x{ih} -> {ow}x{oh}, jobs={jobs}")
    audio = build_master_audio(voices, lead, outro, work, total, cfg)

    Texts = an.Texts(svgrender.font_map(ROOT))
    cache: dict = {}
    seed = abs(hash((ep["season"], ep["day"], ep.get("node", "")))) % 9999 + 1
    n_frames = max(2, int(math.ceil(total * fps)))
    Log(f"[render] composing {n_frames} frames...")
    svgs = []
    for i in range(n_frames):
        svgs.append(an.frame_svg(ep, cfg, shots, i / fps, Texts, cache, seed=seed))
    Log(f"[render] rasterising frames ({(time.time() - t0):.0f}s so far)...")
    frames_dir = work / "frames"
    svgrender.render_frames(svgs, frames_dir, iw, ih, svgrender.font_files(ROOT), jobs, Log)
    svgrender.encode_video(frames_dir, out_path, fps, ow, oh, audio, total, crf=crf, log=Log)
    if not keep_frames:
        shutil.rmtree(frames_dir, ignore_errors=True)
    dur = _probe_dur(out_path)
    Log(f"[render] DONE {out_path.name}  {dur:.1f}s  {out_path.stat().st_size / 1e6:.2f} MB "
        f"({time.time() - t0:.0f}s total)")
    return {"video_path": str(out_path), "duration": dur, "frames": n_frames,
            "shots": len(shots), "render_seconds": round(time.time() - t0, 1)}


def render_stills(cfg: dict, ep: dict, out_dir=None, skip_audio=True, Log=log) -> list[str]:
    """Har line ka ek still (fast visual check / dashboard preview)."""
    out_dir = Path(out_dir or (OUT_DIR / "stills"))
    out_dir.mkdir(parents=True, exist_ok=True)
    voices = []
    for i, line in enumerate(ep["lines"]):
        text = line["text"]
        dur = max(2.4, len(text) / 13.5)
        voices.append({"text": text, "shot": line.get("shot", {}),
                       "words": _estimate_words(text, dur), "dur": dur, "wav": None})
    shots, total, lead = an.build_timeline(ep, cfg, voices)
    Texts = an.Texts(svgrender.font_map(ROOT))
    cache: dict = {}
    seed = abs(hash((ep["season"], ep["day"], ep.get("node", "")))) % 9999 + 1
    import resvg_py

    paths = []
    for i, s in enumerate(shots):
        t = s.start + min(1.1, s.dur * 0.45)
        svg = an.frame_svg(ep, cfg, shots, t, Texts, cache, seed=seed)
        p = out_dir / f"{i:02d}_{(s.meta.get('place') or 'card')}.png"
        p.write_bytes(resvg_py.svg_to_bytes(
            svg_string=svg, font_files=svgrender.font_files(ROOT), skip_system_fonts=True,
            width=540, height=960))
        paths.append(str(p))
    Log(f"[stills] {len(paths)} stills -> {out_dir}")
    return paths


# -------------------------------------------------------------------- main ---

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="state se episode banao + render")
    ap.add_argument("--stills", metavar="DIR", nargs="?", const="",
                    help="sirf stills render karo (fast)")
    ap.add_argument("--jobs", type=int, default=None)
    ap.add_argument("--scale", type=float, default=None, help="preview scale (0.5 = 540x960)")
    ap.add_argument("--keep-frames", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    state = load_state()
    scn = engine.load_scenarios()
    ep = engine.build_episode(state, scn, cfg, None)
    log(f"[main] S{ep['season']} D{ep['day']} {ep['node']} ({ep['kind']}) {len(ep['lines'])} lines")
    if args.stills is not None or args.stills == "":
        render_stills(cfg, ep, args.stills)
    else:
        res = render_episode(cfg, ep, jobs=args.jobs, scale=args.scale,
                             keep_frames=args.keep_frames)
        print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
