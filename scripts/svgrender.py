"""Frame rendering (parallel) + FFmpeg encode."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from common import run  # noqa: F401  (re-export convenience)

FONT_NAMES = ("ArchivoBlack-Regular.ttf", "Barlow-Bold.ttf", "Barlow-Medium.ttf")


def font_files(root: Path):
    return [str(root / "assets" / "fonts" / f) for f in FONT_NAMES]


def font_map(root: Path):
    d = root / "assets" / "fonts"
    return {"bold": d / "ArchivoBlack-Regular.ttf", "med": d / "Barlow-Medium.ttf",
            "caption": d / "Barlow-Bold.ttf"}


# ------------------------------------------------------------------ frames ---

def _render_one(args):
    svg, path, width, height, fonts = args
    import resvg_py

    data = resvg_py.svg_to_bytes(
        svg_string=svg, font_files=fonts, skip_system_fonts=True, width=width, height=height
    )
    with open(path, "wb") as fh:
        fh.write(data)
    return path


def render_frames(svgs, out_dir, width, height, fonts, jobs=4, log=print):
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [str(out_dir / f"f{i:05d}.png") for i in range(len(svgs))]
    tasks = [(s, p, width, height, fonts) for s, p in zip(svgs, paths)]
    jobs = max(1, int(jobs))
    if jobs == 1 or len(tasks) <= 2:
        for i, t in enumerate(tasks):
            _render_one(t)
            if log and i % 60 == 0:
                log(f"    frame {i}/{len(tasks)}")
    else:
        import multiprocessing as mp

        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=jobs) as pool:
            for i, _ in enumerate(pool.imap_unordered(_render_one, tasks, chunksize=2)):
                if log and i % 90 == 0:
                    log(f"    frame {i}/{len(tasks)}")
    return paths


def encode_video(frames_dir, out_path, fps, out_w, out_h, audio_path=None, total=None,
                 crf=20, preset="medium", log=print):
    frame_pat = str(Path(frames_dir) / "f%05d.png")
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-framerate", str(fps), "-i", frame_pat,
    ]
    if audio_path:
        cmd += ["-i", str(audio_path)]
    cmd += [
        "-vf", f"scale={out_w}:{out_h}:flags=lanczos,format=yuv420p",
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
    ]
    if audio_path:
        cmd += ["-c:a", "aac", "-b:a", "160k", "-ac", "2", "-ar", "44100",
                "-map", "0:v:0", "-map", "1:a:0", "-shortest"]
    if total:
        cmd += ["-t", f"{total:.3f}"]
    cmd.append(str(out_path))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{r.stderr[-2000:]}")
    if log:
        log(f"    encoded -> {out_path}")
    return str(out_path)
