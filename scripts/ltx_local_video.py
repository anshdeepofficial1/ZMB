"""LTX-Video inference INSIDE ZMB, not a paid API or pretend 2D renderer.

Uses the original open-source Lightricks image-to-video inference CLI with a
scene-specific approved first frame. Models are cached on the GPU workstation,
not embedded in git. Produces UNREVIEWED cinematic candidate MP4s only.

    python scripts/ltx_local_video.py --day1 --dry-run
    python scripts/ltx_local_video.py --day1 --shot 0 --profile quality \
      --ltx-root .models/LTX-Video --execute

Requires a CUDA GPU + the official LTX-Video repo installed as instructed in
workflows/zmb/LOCAL_VIDEO_MODEL.md. A GitHub CPU runner cannot infer real films.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Sequence

from PIL import Image

from visual_manifest import (
    CAST_BIBLE, PROP_BIBLE, ROOT, build_manifest, day1_episode,
    VisualContractError,
)

OFFICIAL_LTX_REPO = "https://github.com/Lightricks/LTX-Video"
OFFICIAL_LTX_COMMIT = "50f0aef1297574a4b29acbdb874e3a363a6d5f2e"

NEGATIVE_PROMPT = (
    "flat 2d vector cartoon, childish animation, simple stick figures, "
    "robot-like humans, low-poly cutout, plastic skin, wrong face, "
    "changing clothing, shifting car body, warped hands, missing wheels, "
    "deformed limbs, frozen pose, slide show, still-image pan, "
    "jitter, blurred faces, overdark image, oversaturated colors, "
    "text baked into frame, subtitle, logo, watermark, compression blocks"
)


@dataclass(frozen=True)
class Profile:
    name: str
    yaml: str
    width: int
    height: int
    fps: int
    min_vram_gb: int
    max_frames: int = 241


PROFILES = {
    # Diagnostic only. Smaller clips are not an approved professional release.
    "test": Profile("test", "ltxv-2b-0.9.8-distilled.yaml", 448, 800, 24, 8, 121),
    "quality": Profile("quality", "ltxv-2b-0.9.8-distilled.yaml", 704, 1248, 24, 12),
    "studio": Profile("studio", "ltxv-13b-0.9.8-distilled.yaml", 704, 1248, 24, 24),
}


def scene_prompt(shot: dict) -> str:
    """Model-safe photographic brief, locked to the literal narrated action."""
    exact = str(shot.get("physical_direction") or "").strip()
    if len(exact) < 15:
        raise VisualContractError("a physical action description is mandatory")
    return (
        "Premium photorealistic survival-thriller cinema. Consistent real "
        "human anatomy and the exact same character face and wardrobe as "
        "the conditioned first-frame reference; same exact vehicle and "
        "architecture in each adjacent scene. Professionally photographed, "
        "tactile practical environment, sophisticated teal moonlit shadows "
        "and warm amber practical lamps, accurate skin tones, expressive "
        "faces, detailed textures, subtle film grain, high dynamic range "
        "without crushed blacks. MAIN ACTION: " + exact + " "
        "REAL PHYSICAL MOTION: moving parts and characters act exactly as "
        "narrated; visible road movement, correct wheel movement, ignition "
        "failure or moving door handle only if specified in this action. "
        "Controlled camera movement and depth, no arbitrary cuts, no "
        "subject teleportation, no extra people. FRAME: vertical 9:16, "
        "keep people and important props within the central safe region; "
        "leave clean lower-third negative space for captions. "
        "No text, UI overlay, drawing, HUD, watermark or toy animation."
    )


def deterministic_seed(shot: dict) -> int:
    material = json.dumps(
        {"id": shot["id"], "direction": shot["physical_direction"],
         "image": shot["image_path"]}, sort_keys=True
    ).encode("utf-8")
    return int(hashlib.sha256(material).hexdigest()[:8], 16)


def frames_for_seconds(seconds: float, profile: Profile) -> int:
    if not 0.2 < seconds <= 10:
        raise VisualContractError("individual LTX shot length must be 0.2-10 seconds")
    needed = max(9, math.ceil(seconds * profile.fps))
    frames = math.ceil((needed - 1) / 8) * 8 + 1
    if frames > profile.max_frames:
        raise VisualContractError(
            f"{seconds:.2f}s requires {frames} frames but {profile.name} "
            f"supports only {profile.max_frames}; split the action instead"
        )
    return frames


def estimate_seconds(shot: dict) -> float:
    # Planning estimate only: release must use actual Edge TTS durations.
    words = len(str(shot["narration"]).split())
    return round(max(3.0, words / 2.4 + 0.65), 2)


def build_command(ltx_root: Path, shot: dict, profile: Profile, out_dir: Path,
                  *, seconds: float | None = None) -> list[str]:
    duration = estimate_seconds(shot) if seconds is None else seconds
    if profile.width % 32 or profile.height % 32:
        raise VisualContractError("LTX dimensions must be multiples of 32")
    args = [
        sys.executable, str(ltx_root / "inference.py"),
        "--prompt", scene_prompt(shot),
        "--negative_prompt", NEGATIVE_PROMPT,
        "--conditioning_media_paths", str(Path(shot["image_path"]).resolve()),
        "--conditioning_start_frames", "0",
        "--height", str(profile.height),
        "--width", str(profile.width),
        "--num_frames", str(frames_for_seconds(duration, profile)),
        "--frame_rate", str(profile.fps),
        "--seed", str(deterministic_seed(shot)),
        "--pipeline_config", str(ltx_root / "configs" / profile.yaml),
        "--output_path", str(out_dir),
        "--offload_to_cpu", "true",
    ]
    return args


def detect_gpu() -> tuple[str, int]:
    """Return GPU name and GPU VRAM; CPU mode deliberately cannot pass."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True, timeout=15
        )
    except (FileNotFoundError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired) as exc:
        raise VisualContractError(
            "No CUDA video-generation GPU detected. The CPU-only GitHub "
            "runner cannot generate cinematic video. Use a CUDA GPU runner."
        ) from exc
    line = next((x.strip() for x in out.stdout.splitlines() if x.strip()), "")
    if "," not in line:
        raise VisualContractError("nvidia-smi did not provide GPU name and VRAM")
    name, mb = (part.strip() for part in line.rsplit(",", 1))
    return name, int(mb) // 1024


def validate_gpu(profile: Profile, *, experimental_low_vram: bool = False) -> str:
    gpu, vram = detect_gpu()
    if vram < profile.min_vram_gb:
        # Real OS memory offload can sometimes work with low VRAM, but the
        # user must choose an EXPLICIT experimental run; never advertise it
        # as production quality or claim its success without a real test.
        if not experimental_low_vram or profile.name != "test":
            raise VisualContractError(
                f"{gpu}: {vram}GB VRAM detected, {profile.name} profile "
                f"requires about {profile.min_vram_gb}GB for a supported run. "
                "4GB/CPU professional output is not validated. Experimental "
                "offloading is only available with --profile test "
                "--experimental-low-vram, and may still fail."
            )
    return gpu


def verify_source_frame(shot: dict) -> None:
    """No basic cartoons or reference-free text-to-video substitution."""
    from reference_review import verify_reference
    frame = Path(shot["image_path"])
    if not frame.is_file():
        raise VisualContractError(
            f"Missing scene-specific FIRST FRAME {frame}. "
            "Create it using actual approved character and prop identities. "
            "A reusable portrait is not a valid substitute for an action frame."
        )
    try:
        with Image.open(frame) as image:
            w, h = image.size
            if image.format != "PNG":
                raise VisualContractError(f"First frame must be PNG: {frame}")
            image.verify()
    except (OSError, ValueError) as exc:
        raise VisualContractError(f"Invalid first-frame PNG: {frame}") from exc
    if w < 512 or h < 768 or abs(w / h - 9 / 16) > 0.05:
        raise VisualContractError(
            f"First frame must be portrait 9:16 and at least 512x768; "
            f"got {w}x{h}. This is not a verified cinematic source frame."
        )
    cast = json.loads(CAST_BIBLE.read_text(encoding="utf-8"))
    props = json.loads(PROP_BIBLE.read_text(encoding="utf-8"))["props"]
    required_roles = {c["id"] for c in shot["characters"]}
    required_roles.update(p["id"] for p in shot.get("prop_references", []))
    for role in required_roles:
        identity = cast.get(role) or props.get(role)
        if not identity:
            raise VisualContractError(f"Unknown physical identity for {role}")
        verify_reference(role, identity, root=ROOT)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for part in iter(lambda: source.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def generate_shot(ltx_root: Path, shot: dict, profile: Profile, *,
                  experimental_low_vram: bool = False) -> dict:
    verify_source_frame(shot)
    if not (ltx_root / "inference.py").is_file():
        raise VisualContractError(
            f"Official LTX-Video code not installed at {ltx_root}. "
            "Run: python scripts/setup_ltx_video.py --install"
        )
    if not (ltx_root / "configs" / profile.yaml).is_file():
        raise VisualContractError(f"Official model config not present: {profile.yaml}")
    gpu_name = validate_gpu(profile, experimental_low_vram=experimental_low_vram)
    video = Path(shot["video_path"])
    video.parent.mkdir(parents=True, exist_ok=True)
    (ROOT / "work").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / "work", prefix="ltx-") as tmp:
        directory = Path(tmp)
        render_dir = directory / "generated"
        render_dir.mkdir()
        cmd = build_command(ltx_root, shot, profile, render_dir)
        subprocess.run(cmd, cwd=ltx_root, check=True)
        files = sorted(render_dir.rglob("*.mp4"))
        if len(files) != 1:
            raise VisualContractError(
                f"LTX inference expected one candidate MP4, found {len(files)} "
                f"in {render_dir}"
            )
        first = files[0]
        # The official model may generate sub-720p. Label its true native
        # resolution in provenance; never misrepresent scaling as native 1080p.
        subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(first), "-vf",
            "scale=1080:1920:flags=lanczos,setsar=1",
            "-r", "24", "-an", "-c:v", "libx264",
            "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(directory / "final.mp4")
        ], check=True)
        if not (directory / "final.mp4").is_file():
            raise VisualContractError("LTX video transcode did not produce an MP4")
        shutil.move(directory / "final.mp4", video)
    proof = {
        "schema": 1, "shot_id": shot["id"], "model": "Lightricks/LTX-Video",
        "model_config": profile.yaml, "model_commit": OFFICIAL_LTX_COMMIT,
        "actual_gpu": gpu_name, "native_width": profile.width,
        "native_height": profile.height, "delivery_width": 1080,
        "delivery_height": 1920, "upscaled_not_native_1080p": True,
        "seed": deterministic_seed(shot), "source_image_sha256": _sha(Path(shot["image_path"])),
        "video_sha256": _sha(video),
        "physical_direction_sha256": hashlib.sha256(
            shot["physical_direction"].encode("utf-8")
        ).hexdigest(),
        "approval": "UNREVIEWED", "publishing_authorized": False,
    }
    video.with_suffix(".provenance.json").write_text(
        json.dumps(proof, indent=2) + "\n", encoding="utf-8"
    )
    return proof


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--day1", action="store_true", required=True)
    ap.add_argument("--shot", type=int, default=None)
    ap.add_argument("--profile", choices=sorted(PROFILES), default="quality")
    ap.add_argument("--ltx-root", type=Path,
                    default=ROOT / ".models" / "LTX-Video")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print model inference plan without downloading weights")
    ap.add_argument("--execute", action="store_true",
                    help="Perform real local CUDA generation; never Instagram posts")
    ap.add_argument("--experimental-low-vram", action="store_true")
    args = ap.parse_args()
    if args.dry_run and args.execute:
        ap.error("--dry-run and --execute are mutually exclusive")
    if not args.dry_run and not args.execute:
        ap.error("choose --dry-run or --execute explicitly")
    if args.experimental_low_vram and args.profile != "test":
        ap.error("experimental low-VRAM mode only applies to --profile test")
    spec = build_manifest(day1_episode(), allow_unimplemented=True)
    shots = spec["shots"]
    if args.shot is not None:
        if args.shot < 0 or args.shot >= len(shots):
            ap.error(f"--shot must be 0..{len(shots)-1}")
        shots = [shots[args.shot]]
    root = args.ltx_root.expanduser().resolve()
    profile = PROFILES[args.profile]
    for shot in shots:
        cmd = build_command(root, shot, profile, ROOT / "work" / "ltx-test")
        if args.dry_run:
            print(json.dumps({
                "shot": shot["id"], "beat": shot["beat"],
                "action": shot["physical_direction"],
                "frame_input": shot["image_path"], "model": profile.yaml,
                "native_resolution": f"{profile.width}x{profile.height}",
                "fps": profile.fps, "frames": int(cmd[cmd.index("--num_frames")+1]),
                "duration_is_estimate_only": True,
                "release_approved": False,
            }, indent=2))
        else:
            result = generate_shot(
                root, shot, profile,
                experimental_low_vram=args.experimental_low_vram
            )
            print(json.dumps(result, indent=2))
    if args.dry_run:
        print("PLAN ONLY — no model weights downloaded, no cinematic footage generated")
    else:
        print("MP4 candidates generated, but are UNREVIEWED. No Instagram posting.")


if __name__ == "__main__":
    main()
