"""CPU-only technical QA + contact sheet for REAL free-model MP4 clips.

Technical checks cannot detect malformed character anatomy or hallucinated
actions. Every clip remains UNREVIEWED until a human inspects the contact sheet
and playback. This tool never posts to Instagram or calls any AI model.
"""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import statistics
import subprocess

from PIL import Image, ImageChops, ImageDraw, ImageStat

from visual_manifest import VisualContractError

TIMESTAMPS=(0.12,0.60,1.10,1.58,2.04,2.49,2.96,3.60)


def extract(video: Path, at: float) -> Image.Image:
    p=subprocess.run([
        "ffmpeg","-v","error","-ss",f"{at:.3f}",
        "-i",str(video),"-frames:v","1",
        "-f","image2pipe","-vcodec","png","-",
    ],capture_output=True,check=True,timeout=40)
    if len(p.stdout)<4096:
        raise VisualContractError(f"could not decode video at {at:.2f}s")
    return Image.open(io.BytesIO(p.stdout)).convert("RGB")


def analyze(video: Path, output: Path) -> dict:
    if not video.is_file() or video.stat().st_size < 10000:
        raise VisualContractError("no real MP4 received for quality review")
    from free_video_preview import ffprobe
    info=ffprobe(video)
    if info["native_width"]<720 or info["native_height"]<1280:
        raise VisualContractError("rendered output is below minimum portrait delivery size")
    if info["duration"]<3.65:
        raise VisualContractError("render is shorter than a useful 4s scene")
    frames=[extract(video,min(info["duration"]-0.15,t)) for t in TIMESTAMPS]
    samples=[x.resize((135,240)) for x in frames]
    grays=[x.convert("L") for x in samples]
    differences=[
        float(ImageStat.Stat(ImageChops.difference(grays[i],grays[i+1])).mean[0])
        for i in range(len(grays)-1)
    ]
    brightness=[float(ImageStat.Stat(g).mean[0]) for g in grays]
    # Frozen/slideshow clips are rejected at the technical gate. Actual motion
    # in each *physical action* still requires inspecting the footage.
    if statistics.median(differences)<0.8:
        raise VisualContractError(
            "Generated clip appears frozen; cannot call this actual moving footage"
        )
    cols=4
    tile=(205,385)
    sheet=Image.new("RGB",(tile[0]*cols,tile[1]*2),"#0f121b")
    labels=ImageDraw.Draw(sheet)
    for n,frame in enumerate(frames):
        frame=frame.resize((202,359))
        px=(n%cols)*tile[0]
        py=(n//cols)*tile[1]
        sheet.paste(frame,(px+1,py+1))
        labels.text((px+10,py+362),f"{TIMESTAMPS[n]:.2f}s",fill="white")
    output.mkdir(parents=True,exist_ok=True)
    sheet.save(output/"review_contact_sheet.jpg",quality=88)
    report={
        "technical_video": "passed",
        "model_output_production_approved": False,
        "duration_seconds": info["duration"],
        "delivery_width":info["native_width"],
        "delivery_height":info["native_height"],
        "frame_sample_times_seconds":list(TIMESTAMPS),
        "motion_pixel_difference_median_8bit":round(statistics.median(differences),2),
        "motion_pixel_difference_by_interval": [round(x,2) for x in differences],
        "mean_luma_by_sample": [round(x,2) for x in brightness],
        "qa_limitations": [
            "Pixel differences are NOT proof of car wheel/road movement.",
            "Cannot infer face continuity, body anatomy or realistic physics.",
            "Cannot guarantee film colour style, shot coherence or captions.",
            "Human must watch MP4 and compare each shot to narrated action."
        ],
        "publishing_authorized":False,
    }
    (output/"quality_report.json").write_text(
        json.dumps(report,indent=2)+"\n",encoding="utf-8"
    )
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--video",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    opts=p.parse_args()
    print(json.dumps(analyze(opts.video,opts.output),indent=2))


if __name__=="__main__":
    main()
