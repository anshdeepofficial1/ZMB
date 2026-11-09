"""One REAL image-to-video experiment using only Hugging Face FREE ZeroGPU.

Input is the original PNG artifact generated on a GitHub runner. The MP4
remains an UNREVIEWED preview, and is NEVER a publishable scene. A production
scene still needs face/prop and motion continuity review.

No paid API calls, local GPU, account rotation, synthetic fallback, or
publishing credentials.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from visual_manifest import build_manifest, day1_episode, VisualContractError, ROOT
from free_first_frame import verify_quota
from hf_zerogpu_video import space_info, _extract_video_path

SPACE = "Lightricks/LTX-2.5"
OUT = ROOT / "out" / "free_motion"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_source(shot: dict, image: Path) -> dict:
    from PIL import Image
    if not image.is_file():
        raise VisualContractError(f"first frame missing: {image}")
    sidecar = image.with_suffix(".json")
    if not sidecar.is_file():
        raise VisualContractError(
            "first frame has no original FLUX model provenance; "
            "will not animate unverified input."
        )
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    if data.get("shot_id") != shot["id"]:
        raise VisualContractError("first frame is for a different authored scene")
    digest = sha256(image)
    if digest != data.get("file_sha256"):
        raise VisualContractError("first-frame bytes changed since model generation")
    if data.get("model_space") != "black-forest-labs/FLUX.1-schnell":
        raise VisualContractError("first frame is not the original free FLUX model")
    from art_direction import STYLE_ID
    if data.get("art_style") != STYLE_ID:
        raise VisualContractError(
            "Cannot animate old photorealistic source image. Generate a NEW "
            "premium 3D animated first frame with matching style provenance."
        )
    with Image.open(image) as picture:
        w, h = picture.size
        if picture.format != "PNG" or w < 512 or h < 768:
            raise VisualContractError("first frame is not a real high-resolution PNG")
        if abs(w / h - 9 / 16) > 0.05:
            raise VisualContractError("first frame must be 9:16 portrait")
        picture.verify()
    return {"sha256": digest, "image_width": w, "image_height": h}


def prompt_for_real_motion(shot: dict) -> str:
    """Physically coherent premium CGI animation, not live-action footage."""
    from art_direction import animation_prompt
    return animation_prompt(shot)


def ffprobe(path: Path) -> dict:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "stream=codec_type,width,height,avg_frame_rate:format=duration",
        "-of", "json", str(path),
    ]
    p = subprocess.run(cmd, text=True, capture_output=True, check=True, timeout=30)
    data = json.loads(p.stdout)
    videos = [x for x in data.get("streams", []) if x.get("codec_type") == "video"]
    if len(videos) != 1:
        raise VisualContractError("inference output must have exactly one video track")
    v = videos[0]
    w,h = int(v["width"]), int(v["height"])
    duration = float(data.get("format", {}).get("duration") or 0)
    if w < 384 or h < 640 or abs(w/h-9/16) > 0.06:
        raise VisualContractError(f"free model output invalid portrait size {w}x{h}")
    if not 3.0 <= duration <= 6.0:
        raise VisualContractError(f"free model output invalid duration: {duration:.2f}s")
    return {"native_width": w, "native_height": h, "duration": duration}


def encode_preview(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True,exist_ok=True)
    ffmpeg = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source),
        "-vf",
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,fps=24,setsar=1,"
        "eq=contrast=1.06:saturation=1.10,"
        "drawbox=x=18:y=115:w=520:h=62:color=black@0.46:t=fill,"
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        "text='UNREVIEWED - FREE MODEL TEST':"
        "fontcolor=white:fontsize=28:x=35:y=129",
        "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264",
        "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        str(dest),
    ]
    subprocess.run(ffmpeg, check=True, timeout=300)


def generate_one(shot: dict, first_frame: Path, output: Path) -> dict:
    first = verify_source(shot, first_frame)
    token = os.environ.get("HF_TOKEN", "")
    account = verify_quota(token)
    status = space_info()
    if status["stage"].upper() != "RUNNING" or not status["free_zero_gpu_verified"]:
        raise VisualContractError(
            "Official free LTX-2.5 Space is offline or not confirmed ZeroGPU. "
            "No paid fallback available."
        )
    from gradio_client import Client, handle_file
    client = Client(SPACE, token=token, verbose=False)
    print(
        f"[free] starting ONE real original video from approved-for-TEST "
        f"source shot {shot['id']}; account is verified Free, no money spent",
        flush=True,
    )
    result = client.predict(
        prompt_for_real_motion(shot),
        handle_file(str(first_frame)),
        896, 512,
        4.0,
        42,
        "conv",
        False,
        False,
        False,
        api_name="/run",
    )
    raw = _extract_video_path(result)
    native = ffprobe(raw)
    output.mkdir(parents=True,exist_ok=True)
    draft = output / f"shot_{shot['index']:02d}_UNREVIEWED.mp4"
    encode_preview(raw, draft)
    final = ffprobe(draft)
    if final["native_width"] != 1080 or final["native_height"] != 1920:
        raise VisualContractError("1080x1920 delivery export failed")
    proof = {
        "shot_id": shot["id"],
        "model": SPACE,
        "art_style": __import__("art_direction").STYLE_ID,
        "source_image_sha256": first["sha256"],
        "native_model_size": f"{native['native_width']}x{native['native_height']}",
        "delivery_size": "1080x1920 (scaled; not native)",
        "duration_seconds": final["duration"],
        "free_only": True,
        "quota_before_seconds": account.get("remaining_before"),
        "video_sha256": sha256(draft),
        "status": "UNREVIEWED",
        "publishing_authorized": False,
        "paid_rupees": 0,
    }
    draft.with_suffix(".json").write_text(
        json.dumps(proof,indent=2)+"\n",encoding="utf-8"
    )
    return proof


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=("plan","video"),default="plan")
    parser.add_argument("--shot",type=int,default=0)
    parser.add_argument("--source",type=Path)
    parser.add_argument("--accept-free-quota",action="store_true")
    opts=parser.parse_args()
    shots=build_manifest(day1_episode(),allow_unimplemented=True)["shots"]
    if not 0<=opts.shot<len(shots):
        parser.error("invalid shot index")
    shot=shots[opts.shot]
    if opts.mode=="plan":
        print(json.dumps({
            "shot_id":shot["id"], "model":SPACE, "video_seconds":4,
            "free_only":True,"camera_direction":prompt_for_real_motion(shot),
            "publishing_authorized":False,
        },indent=2))
        return
    if not opts.accept_free_quota or opts.source is None:
        parser.error("video requires source PNG and explicit free quota authorization")
    print(json.dumps(generate_one(shot, opts.source, OUT),indent=2))
    print("EXPERIMENTAL CLIP ONLY. HUMAN VISUAL INSPECTION REQUIRED.")


if __name__=="__main__":
    main()
