"""Generate ONE photorealistic cinematic first frame on FREE Hugging Face ZeroGPU.

This runs inside GitHub Actions, never on the user's laptop. This is an
UNREVIEWED candidate and cannot authorize publishing or production video.
No billing endpoint, paid fallback, or multiple-account quota bypass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

from PIL import Image

from visual_manifest import build_manifest, day1_episode, VisualContractError, ROOT

MODEL = "black-forest-labs/FLUX.1-schnell"
OUT = ROOT / "out" / "free_first_frame"
WIDTH = 768
HEIGHT = 1376  # 9:16 portrait within model's 32-pixel grid


def frame_prompt(shot: dict) -> str:
    if int(shot["index"]) == 0:
        camera = (
            "Dramatic medium-close low three-quarter FRONT tracking camera, "
            "steel-blue four-door sedan fills center 75% of portrait composition. "
            "Visible front wheels firmly on road, realistic headlamp reflections "
            "and lane markings, driver Max discernible through windscreen. "
            "No floating car, no aerial camera, no landscape framed too wide. "
        )
    else:
        camera = (
            "Portrait close-to-medium live-action story frame, characters and "
            "required props centrally visible and scale believable. "
        )
    characters = " ".join(
        f"{a['id'].upper()}: {a['identity']}. "
        for a in shot.get("characters", [])
    )
    props = " ".join(
        f"PERMANENT PROP {a['id'].upper()}: {a['identity']}. "
        for a in shot.get("prop_references", [])
    )
    return (
        "ONE SINGLE FRAME from an expensive photorealistic survival-horror "
        "feature film. Live-action cinematography, not animation. "
        "Frame 9:16 vertical cinematic composition. The fixed narrator action "
        "is exactly: " + shot["physical_direction"] + ". " +
        camera + characters + props +
        "Deep moonlit teal blue environment, distinct warm amber halogen "
        "lamps and headlights, detailed night fog, rich photographic contrast "
        "without dark empty frame, visible natural material texture, accurate "
        "anatomy and physical perspective, 35mm cinema lens, professional "
        "colour grading with neutral skin tones, restrained film grain. "
        "One cohesive place and one continuous believable scene, not collage. "
        "No title, no letterforms, no logo, no subtitle, no HUD, no watermark, "
        "no plastic/cartoon/illustrated people, no robot, no drawn outlines, "
        "no cheap 3D game render, no empty upper half of frame."
    )


def _result_file(result) -> Path:
    data = result[0] if isinstance(result, (tuple, list)) else result
    if isinstance(data, dict):
        data = data.get("path") or data.get("name") or data.get("image")
    if not isinstance(data, str) or not data:
        raise VisualContractError(
            "The free FLUX demo did not return a downloadable image file."
        )
    file = Path(data)
    if not file.is_file() or file.stat().st_size < 4000:
        raise VisualContractError("Free FLUX image output missing or empty")
    return file


def verify_quota(token: str) -> dict:
    if not token.startswith("hf_"):
        raise VisualContractError(
            "GitHub repository secret HF_TOKEN required (free Hugging Face)."
        )
    from huggingface_hub import HfApi
    try:
        quota = HfApi(token=token).get_zero_gpu_quota()
    except Exception as exc:
        raise VisualContractError(
            "Could not read free ZeroGPU quota. The HF token may need "
            "'Billing: read usage' permission; no inference attempted."
        ) from exc
    base = float(getattr(quota, "base", 0) or 0)
    remaining = float(getattr(quota, "remaining", 0) or 0)
    if base <= 0 or base > 300:
        raise VisualContractError(
            f"Free-only mode requires the 300-second/day account tier; "
            f"detected quota base {base}. No paid account inference."
        )
    if remaining < 35:
        raise VisualContractError(
            f"Only {remaining:.0f}s free quota remain; need at least 35s "
            "before requesting an image. No paid fallback."
        )
    return {"base": base, "remaining_before": remaining}


def generate(shot: dict, destination: Path) -> dict:
    token = os.environ.get("HF_TOKEN", "")
    quota = verify_quota(token)
    from hf_zerogpu_video import space_info as _video_space_info
    # Only the user's free daily shared quota can be charged.
    # No paid inference SDK or cloud billing key is imported.
    from gradio_client import Client
    print(
        f"[free] requesting ONE real original 9:16 first frame for shot "
        f"{shot['id']} from {MODEL}", flush=True
    )
    client = Client(MODEL, token=token, verbose=False)
    # Official FLUX.1-Schnell Space: infer(prompt, seed, randomize_seed,
    #                                      width, height, num_inference_steps).
    seed = int(hashlib.sha256(
        (shot["id"] + shot["prompt"]).encode("utf-8")
    ).hexdigest()[:7], 16)
    result = client.predict(
        frame_prompt(shot),
        seed,
        False,
        WIDTH,
        HEIGHT,
        4,
        api_name="/infer",
    )
    generated = _result_file(result)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(generated) as image:
        image.load()
        if image.width < 512 or image.height < 768:
            raise VisualContractError(
                f"Model image too small: {image.width}x{image.height}"
            )
        if abs(image.width / image.height - 9 / 16) > 0.045:
            raise VisualContractError(
                f"Model did not return 9:16 portrait: {image.size}"
            )
        image.convert("RGB").save(destination, format="PNG", optimize=True)
    if destination.stat().st_size < 10000:
        raise VisualContractError("Free first frame has suspiciously tiny data")
    proof = {
        "shot_id": shot["id"],
        "file_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "model_space": MODEL,
        "original_generated_width": WIDTH, "original_generated_height": HEIGHT,
        "free_quota_before_seconds": quota["remaining_before"],
        "character_identity_status": "UNREVIEWED",
        "motion_status": "NOT_GENERATED",
        "instagram_publishing_authorized": False,
        "amount_paid_rupees": 0,
    }
    destination.with_suffix(".json").write_text(
        json.dumps(proof, indent=2) + "\n", encoding="utf-8"
    )
    return proof


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("plan", "image"), default="plan")
    ap.add_argument("--shot", type=int, default=0)
    ap.add_argument("--accept-free-quota", action="store_true")
    args = ap.parse_args()
    shots = build_manifest(day1_episode(), allow_unimplemented=True)["shots"]
    if not 0 <= args.shot < len(shots):
        ap.error(f"shot must be between 0 and {len(shots)-1}")
    shot = shots[args.shot]
    if args.mode == "plan":
        print(json.dumps({
            "mode": "plan", "cost_rupees": 0, "model": MODEL,
            "shot_id": shot["id"], "resolution": f"{WIDTH}x{HEIGHT}",
            "source_prompt": frame_prompt(shot),
            "motion_created": False,
            "publishing_authorized": False,
        }, indent=2))
        return
    if not args.accept_free_quota:
        ap.error("Explicit --accept-free-quota required; otherwise no GPU call")
    output = OUT / f"shot_{args.shot:02d}.png"
    print(json.dumps(generate(shot, output), indent=2))
    print(f"UNREVIEWED FIRST FRAME: {output}")


if __name__ == "__main__":
    main()
