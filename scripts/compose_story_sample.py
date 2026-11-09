"""Add genuine English narration and safe-zone subtitles to real LTX footage.

Preview-only: never silently loops 4s footage to cover long narration,
never uses fake timings, never posts or marks a shot approved.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

from visual_manifest import ROOT, VisualContractError, build_manifest, day1_episode
from render_cinematic import build_subtitles
from free_video_preview import ffprobe
from inspect_free_motion import analyze
import render

OUT = ROOT / "out" / "review_sample"


def duration(path: Path) -> float:
    proc=subprocess.run([
        "ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1",str(path)
    ],check=True,text=True,capture_output=True,timeout=30)
    return float(proc.stdout.strip())


def voice_for_shot(text: str, target: float, work: Path) -> tuple[Path,list]:
    """Honest word timings; increase speaking speed only if all words fit."""
    work.mkdir(parents=True,exist_ok=True)
    for rate in ("+0%","+15%","+30%"):
        source=work/f"voice_{rate.replace('+','')}.mp3"
        words=asyncio.run(render._tts_line(
            text,"en-US-ChristopherNeural",rate,source
        ))
        if not words:
            raise VisualContractError("Narration has no exact Edge TTS word boundaries")
        spoken=duration(source)
        if spoken <= target-0.04 and float(words[-1]["end"]) <= target-0.05:
            return source,words
    raise VisualContractError(
        "Narration exceeds the physical 4-second model clip. "
        "Cannot hide this with freeze, loop or cropped speech."
    )


def compose(video: Path, shot_index: int, output: Path=OUT) -> dict:
    shots=build_manifest(day1_episode(),allow_unimplemented=True)["shots"]
    if not 0<=shot_index<len(shots):
        raise VisualContractError("invalid story line index")
    info=ffprobe(video)
    if info["native_width"]!=1080 or info["native_height"]!=1920:
        raise VisualContractError("source must be an actual verified 1080x1920 preview")
    text=shots[shot_index]["narration"]
    output.mkdir(parents=True,exist_ok=True)
    work=output/"work"
    voice,words=voice_for_shot(text,info["duration"],work)
    ass=work/"captions.ass"
    line=SimpleNamespace(
        kind="line",start=0.0,end=info["duration"],dur=info["duration"]
    )
    build_subtitles([line],[{"text":text,"words":words}],ass)
    final=output/f"shot_{shot_index:02d}_with_voice_UNREVIEWED.mp4"
    command=[
        "ffmpeg","-y","-hide_banner","-loglevel","error",
        "-i",str(video),"-i",str(voice),
        "-filter_complex",
        "[0:a:0]volume=0.06[amb];[1:a:0]volume=1.25[narr];"
        "[amb][narr]amix=inputs=2:duration=first:"
        "dropout_transition=0[a]",
        "-vf",f"ass={ass.as_posix()}",
        "-map","0:v:0","-map","[a]",
        "-c:v","libx264","-preset","medium","-crf","18",
        "-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","160k",
        "-t",f"{info['duration']:.3f}",
        "-movflags","+faststart",str(final),
    ]
    subprocess.run(command,check=True,timeout=240)
    result=ffprobe(final)
    if abs(result["duration"]-info["duration"])>0.15:
        raise VisualContractError("final caption/audio video duration changed unexpectedly")
    sha=hashlib.sha256(final.read_bytes()).hexdigest()
    qa=analyze(final,output)
    report={
        "shot_id":shots[shot_index]["id"],
        "video_sha256":sha,
        "actual_moving_video_duration_seconds":result["duration"],
        "english_narration":text,
        "word_timed_captions":len(words),
        "subtitle_position":"Instagram-safe lower third",
        "non_looped":True,
        "technical_qa":qa["technical_video"],
        "photorealism_and_character_continuity":"UNREVIEWED",
        "publishing_authorized":False,
        "zero_extra_cost":True,
    }
    (output/"narrated_sample.json").write_text(
        json.dumps(report,indent=2)+"\n",encoding="utf-8"
    )
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--video",required=True,type=Path)
    parser.add_argument("--shot",type=int,default=0)
    args=parser.parse_args()
    print(json.dumps(compose(args.video,args.shot),indent=2))


if __name__=="__main__":
    main()
