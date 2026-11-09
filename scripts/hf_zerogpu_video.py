"""STRICTLY FREE, experimental ZeroGPU cinematic inference from GitHub Actions.

This is NOT a production-reliable provider: free Hugging Face accounts have a
shared daily GPU quota, third-party demos may change their Gradio API at any
time, and the video still needs manual review. No paid inference endpoints,
billing keys, or quota-circumvention logic are used.

Available actions:
    python scripts/hf_zerogpu_video.py --mode plan
    python scripts/hf_zerogpu_video.py --mode probe
    python scripts/hf_zerogpu_video.py --mode one_clip --shot 0 --use-free-quota

The final action requires HF_TOKEN for a *free* Hugging Face account and an
approved scene-specific first-frame PNG. Never posts to Instagram.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import requests

from visual_manifest import ROOT, build_manifest, day1_episode, VisualContractError

SPACE = "Lightricks/LTX-2.5"
SPACE_API = f"https://huggingface.co/api/spaces/{SPACE}"
MODEL = "Lightricks/LTX-2.5 (official free ZeroGPU demo)"
DAILY_FREE_SECONDS = 300
MINIMUM_REMAINING_SECONDS = 200  # conservative reserve for xlarge 2x GPU quota
OUT = ROOT / "out" / "free_zerogpu"


def planned() -> dict:
    return {
        "budget_rupees": 0,
        "provider": "Hugging Face ZeroGPU (shared free quota)",
        "model_space": SPACE,
        "video_model": MODEL,
        "monthly_paid_api_calls": 0,
        "clips_per_invocation_max": 1,
        "authentication": "free HF_TOKEN required for actual inference",
        "free_account_gpu_quota_seconds_per_day": DAILY_FREE_SECONDS,
        "model_clip_seconds": 4,
        "model_demo_may_pause_or_change": True,
        "minimum_quota_before_one_clip": MINIMUM_REMAINING_SECONDS,
        "paid_fallback_allowed": False,
        "instagram_publishing": False,
        "guaranteed_daily_full_episode": False,
        "quality_approved": False,
    }


def space_info() -> dict:
    """Probe public Space metadata without reserving GPU time or spending money."""
    response = requests.get(
        SPACE_API, timeout=25, headers={"Accept": "application/json"}
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise VisualContractError("Hugging Face Space returned non-object metadata")
    runtime = data.get("runtime") or {}
    stage = str(runtime.get("stage") or data.get("stage") or "UNKNOWN")
    hardware = str(
        runtime.get("hardware")
        or runtime.get("requestedHardware")
        or data.get("hardware")
        or "UNKNOWN"
    )
    if data.get("private"):
        raise VisualContractError("Selected free ZeroGPU demo is now private")
    if data.get("disabled") or data.get("gated"):
        raise VisualContractError("Selected free ZeroGPU demo is unavailable")
    # Do not claim a verified ZeroGPU service without authoritative metadata.
    return {
        "space": SPACE,
        "stage": stage,
        "hardware": hardware,
        "public": not bool(data.get("private")),
        "free_zero_gpu_verified": "zero" in hardware.lower(),
        "no_inference_requested": True,
        "billable_calls": 0,
    }


def approved_scene(shot: dict) -> Path:
    """Require review of original exact image, actor and vehicle references."""
    from first_frame_review import verify_frame
    from reference_review import verify_reference
    image = Path(shot["image_path"])
    if not image.is_file():
        raise VisualContractError(
            f"Scene image not yet generated: {image}. No character-consistent "
            "video can be created until first-frame reference is reviewed."
        )
    # verify_frame also validates original character/prop reference hashes.
    verify_frame(shot)
    return image


def _free_account_quota(token: str) -> dict:
    from huggingface_hub import HfApi
    api = HfApi(token=token)
    # Free tier: never ask a paid Inference Endpoint for GPU work.
    info = api.get_zero_gpu_quota()
    remaining = int(getattr(info, "remaining", 0) or 0)
    base = int(getattr(info, "base", 0) or 0)
    if base > DAILY_FREE_SECONDS:
        raise VisualContractError(
            "Account may have a paid/extended ZeroGPU allowance. "
            "ZMB only supports the explicitly FREE 5-minute daily tier."
        )
    if remaining < MINIMUM_REMAINING_SECONDS:
        raise VisualContractError(
            f"Free ZeroGPU quota remaining {remaining}s, less than "
            f"{MINIMUM_REMAINING_SECONDS}s required for one attempt. "
            "No paid fallback, quota bypass, or alternate account allowed."
        )
    return {"remaining": remaining, "base": base}


def _extract_video_path(result) -> Path:
    # Gradio gr.Video outputs are typically a temporary local file path,
    # sometimes wrapped in dict or tuple with an HTML metadata panel.
    data = result[0] if isinstance(result, (list, tuple)) else result
    if isinstance(data, dict):
        data = data.get("video") or data.get("path") or data.get("name")
    if not isinstance(data, str) or not data:
        raise VisualContractError("Gradio model response contains no video filepath")
    path = Path(data).expanduser()
    if not path.is_file() or path.stat().st_size < 2048:
        raise VisualContractError("Gradio did not download a real output MP4")
    with path.open("rb") as stream:
        if b"ftyp" not in stream.read(64):
            raise VisualContractError("Gradio returned a file that is not an MP4")
    return path


def generate_one_clip(shot: dict, *, token: str, output: Path) -> dict:
    if not token.startswith("hf_"):
        raise VisualContractError(
            "Missing free Hugging Face personal token. Save as GitHub "
            "repository secret HF_TOKEN, not a code file."
        )
    first_frame = approved_scene(shot)
    status = space_info()
    if not status["public"] or status["stage"].upper() != "RUNNING":
        raise VisualContractError(
            f"Free model demo unavailable ({status['stage']}). "
            "No paid or non-free fallback will be used."
        )
    if not status["free_zero_gpu_verified"]:
        raise VisualContractError(
            f"Unable to verify free ZeroGPU hardware ({status['hardware']}). "
            "Refusing to risk a paid endpoint."
        )
    quota = _free_account_quota(token)
    try:
        from gradio_client import Client, handle_file
    except ImportError as exc:
        raise VisualContractError(
            "Install gradio_client from scripts/requirements-free.txt"
        ) from exc
    # Exactly ONE 4-second 9:16 clip per manual request. The official
    # model uses an xlarge ZeroGPU reservation at double quota cost.
    # No retries, alternative identities, or billing fallbacks.
    client = Client(SPACE, token=token, verbose=False)
    result = client.predict(
        str(shot["physical_direction"]),  # exact narrated action
        handle_file(str(first_frame)),   # approved scene first frame
        896,  # height, divisible by 64, near 9:16
        512,  # width, divisible by 64
        4.0,  # official 1-5 second demo slider
        42,   # stable seed
        "conv",  # fast VAE video decoder
        False,   # no unpredictable auto duration
        False,   # don't randomize seed
        False,   # no enhancer rewriting approved action
        api_name="/run",
    )
    generated = _extract_video_path(result)
    destination = output / f"{int(shot['index']):02d}_UNREVIEWED.mp4"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(generated, destination)
    sha = hashlib.sha256(destination.read_bytes()).hexdigest()
    result_info = {
        "file": str(destination),
        "sha256": sha,
        "shot_id": shot["id"],
        "model": MODEL,
        "zero_gpu_remaining_before": quota["remaining"],
        "free_only": True,
        "cost_rupees": 0,
        "review": "UNREVIEWED",
        "publishing_authorized": False,
    }
    destination.with_suffix(".json").write_text(
        json.dumps(result_info, indent=2) + "\n", encoding="utf-8"
    )
    return result_info


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["plan", "probe", "one_clip"], default="plan")
    parser.add_argument("--shot", type=int, default=0)
    parser.add_argument("--use-free-quota", action="store_true")
    args = parser.parse_args()
    if args.mode == "plan":
        document=planned()
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/"plan.json").write_text(json.dumps(document,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(document, indent=2))
        return
    if args.mode == "probe":
        status = space_info()
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/"probe.json").write_text(json.dumps(status,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(status, indent=2))
        if not status["free_zero_gpu_verified"]:
            print("Free GPU hardware not confirmed; experimental clip disabled.")
        return
    if not args.use_free_quota:
        parser.error("one_clip requires explicit --use-free-quota")
    shots = build_manifest(day1_episode(), allow_unimplemented=True)["shots"]
    if not 0 <= args.shot < len(shots):
        parser.error(f"shot must be between 0 and {len(shots)-1}")
    token = os.environ.get("HF_TOKEN", "")
    info = generate_one_clip(shots[args.shot], token=token, output=OUT)
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
