"""Verify an actual code-drawn 2D MP4, not a still slide or silent placeholder.

Zero AI, zero cloud inference. Checks the exported video/audio and visible
motion in the central scene area; visual artistic review is still required.
"""
from __future__ import annotations

import argparse
from array import array
import json
import math
from pathlib import Path
import subprocess


def _run(*cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, check=True, timeout=120)


def inspect(video: Path) -> dict:
    if not video.is_file() or video.stat().st_size < 100_000:
        raise ValueError("MP4 missing or empty")
    probe = _run("ffprobe", "-v", "error", "-show_streams", "-show_format",
                 "-of", "json", str(video))
    info = json.loads(probe.stdout)
    tracks = info.get("streams") or []
    pictures = [x for x in tracks if x.get("codec_type") == "video"]
    audios = [x for x in tracks if x.get("codec_type") == "audio"]
    if len(pictures) != 1 or len(audios) != 1:
        raise ValueError("Expected exactly one video and one narration track")
    width, height = int(pictures[0].get("width", 0)), int(pictures[0].get("height", 0))
    duration = float((info.get("format") or {}).get("duration") or 0)
    if (width, height) != (1080, 1920):
        raise ValueError(f"Expected portrait 1080x1920, got {width}x{height}")
    if not 20 <= duration <= 180:
        raise ValueError(f"Unexpected episode duration {duration:.2f}s")
    if pictures[0].get("codec_name") != "h264":
        raise ValueError("Expected H.264 video")
    # The middle of the frame contains the acting and props, not just captions.
    # Sampling at 1 fps catches true frame-to-frame scene animation.
    pixel_width, pixel_height = 96, 104
    sample = _run(
        "ffmpeg", "-v", "error", "-i", str(video),
        "-vf", "fps=1,crop=iw*0.7:ih*0.45:iw*0.15:ih*0.27,scale=96:104,format=gray",
        "-pix_fmt", "gray", "-f", "rawvideo", "-an", "-",
    ).stdout
    frame_size = pixel_width * pixel_height
    frames = [sample[i:i + frame_size] for i in range(0, len(sample), frame_size)]
    frames = [f for f in frames if len(f) == frame_size]
    if len(frames) < 15:
        raise ValueError("Not enough decoded frames for movement inspection")
    movement = [
        sum(abs(a - b) for a, b in zip(left, right)) / frame_size
        for left, right in zip(frames[:-1], frames[1:])
    ]
    active = sum(x > 2.0 for x in movement)
    if active < max(5, int(len(movement) * 0.18)):
        raise ValueError(
            f"Central character/action region appears static: {active} changing intervals"
        )
    pcm = _run("ffmpeg", "-v", "error", "-i", str(video),
               "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-").stdout
    samples = array("h")
    samples.frombytes(pcm[:len(pcm) - len(pcm) % 2])
    if not samples:
        raise ValueError("Narration audio decoded to zero samples")
    audio_rms = math.sqrt(sum(int(s) * int(s) for s in samples) / len(samples)) / 32768.0
    if audio_rms < 0.001:
        raise ValueError("Narration audio is silent or nearly silent")
    return {
        "codec": "h264", "portrait": f"{width}x{height}",
        "duration_seconds": round(duration, 3),
        "seconds_sampled": len(frames),
        "changing_scene_intervals": active,
        "motion_peak_luma": round(max(movement), 3),
        "audio_rms": round(audio_rms, 6),
        "animation_method": "original_2d_svg_resvg_ffmpeg_no_ai",
        "human_visual_review": "REQUIRED",
        "publishing_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--report", type=Path, default=Path("out/2d_qa_report.json"))
    args = parser.parse_args()
    result = inspect(args.video)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
