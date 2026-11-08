"""GitHub Actions-operated cinematic Day 1 preview with real cloud GPU inference.

All orchestration and media assembly run on a GitHub-hosted Ubuntu runner.
fal.ai performs model inference off-runner because standard GitHub Actions
have no CUDA GPU. No laptop, fake vector footage, or Instagram posting.

Explicit opt-in to paid calls is mandatory. Outputs are NEVER APPROVED.
    python scripts/github_cloud_video.py --mode plan
    python scripts/github_cloud_video.py --mode shot --shot 0 --authorize-charges
    python scripts/github_cloud_video.py --mode day1 --authorize-charges
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
from urllib.parse import urlsplit

import requests
from PIL import Image

from common import ROOT, load_config, run
from visual_manifest import (
    CAST_BIBLE, PROP_BIBLE, build_manifest, day1_episode, VisualContractError
)

IMAGE_MODEL = "fal-ai/flux-2-pro"
EDIT_MODEL = "fal-ai/nano-banana-2/edit"
VIDEO_MODEL = "fal-ai/ltx-2.3/image-to-video"
WORK = ROOT / "work" / "github_cinematic"
OUTPUT = ROOT / "out" / "github_cinematic"
ALLOWED_MEDIA_HOSTS = ("fal.media", "storage.googleapis.com", "storage.cloud.google.com")
DEFAULT_MAX_CALLS = 24


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for part in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def identity_bibles() -> dict:
    cast = json.loads(CAST_BIBLE.read_text(encoding="utf-8"))
    props = json.loads(PROP_BIBLE.read_text(encoding="utf-8"))["props"]
    return {**cast, **props}


def required_roles(shots: list[dict]) -> list[str]:
    found = set()
    for shot in shots:
        found.update(x["id"] for x in shot.get("characters", []))
        found.update(x["id"] for x in shot.get("prop_references", []))
    return sorted(found)


def preflight_plan(shots: list[dict], *, max_calls: int = DEFAULT_MAX_CALLS) -> dict:
    if not shots:
        raise VisualContractError("no authored cinematic shots")
    roles = required_roles(shots)
    bibles = identity_bibles()
    if not all(role in bibles for role in roles):
        raise VisualContractError("some story roles have no visual identity definitions")
    # New characters/props each require 1 initial reference generation.
    # Each scene needs 1 reference-conditioned first-frame + 1 real video.
    calls = len(roles) + 2 * len(shots)
    if calls > max_calls:
        raise VisualContractError(
            f"generation needs {calls} billable calls, exceeds safe cap {max_calls}; "
            "choose a smaller shot range or increase an explicit cap"
        )
    return {
        "roles": roles, "shots": len(shots), "billable_api_calls_max": calls,
        "cost_amount": "provider-priced; no fixed or guaranteed total",
        "reference_model": IMAGE_MODEL, "frame_model": EDIT_MODEL,
        "video_model": VIDEO_MODEL, "format": "1080x1920 portrait 9:16",
        "published": False, "reviewed": False,
    }


def _allowed_download_url(url: str) -> bool:
    try:
        p = urlsplit(url)
    except ValueError:
        return False
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        return False
    host = p.hostname.lower()
    return any(host == domain or host.endswith("." + domain)
               for domain in ALLOWED_MEDIA_HOSTS)


def download_provider_asset(url: str, path: Path, suffix: str) -> None:
    """Download only trusted provider media hosts; never arbitrary URLs."""
    if not _allowed_download_url(url):
        raise VisualContractError("model returned an untrusted or non-HTTPS media URL")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".partial")
    total = 0
    try:
        with requests.get(url, stream=True, timeout=(20, 100),
                          allow_redirects=False) as response:
            response.raise_for_status()
            if response.is_redirect:
                raise VisualContractError("remote model redirected media to another domain")
            with temp.open("wb") as out:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > 300_000_000:
                        raise VisualContractError("provider asset exceeds 300MB limit")
                    out.write(chunk)
        if total < 2048:
            raise VisualContractError(f"model returned empty/tiny {suffix} media")
        with temp.open("rb") as stream:
            magic = stream.read(64)
        if suffix == ".png" and magic[:8] != b"\x89PNG\r\n\x1a\n":
            raise VisualContractError("provider failed to supply the requested PNG")
        if suffix == ".mp4" and b"ftyp" not in magic:
            raise VisualContractError("provider failed to supply a real MP4")
        if suffix == ".png":
            with Image.open(temp) as img:
                img.verify()
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def _first_media_url(result: dict, *, kind: str) -> str:
    if kind == "image":
        images = result.get("images") or []
        item = images[0] if isinstance(images, list) and images else None
    else:
        item = result.get("video")
    if not isinstance(item, dict) or not _allowed_download_url(item.get("url", "")):
        raise VisualContractError(f"no trustworthy {kind} media URL in model output")
    return str(item["url"])


class FalInference:
    """One paid call per explicit request, with bounded queue wait and no retry spending."""
    def __init__(self):
        if not os.environ.get("FAL_KEY", "").strip():
            raise VisualContractError(
                "FAL_KEY GitHub Actions secret is missing; no external "
                "GPU generation can begin"
            )
        try:
            import fal_client
        except ImportError as exc:
            raise VisualContractError(
                "fal-client not installed; install scripts/requirements-cloud.txt"
            ) from exc
        self.fal = fal_client

    def generate(self, model: str, payload: dict, *, kind: str,
                 destination: Path) -> dict:
        print(f"[cloud] requesting {kind} from {model}: {destination.name}", flush=True)
        result = self.fal.subscribe(
            model, arguments=payload, with_logs=False, client_timeout=900,
            start_timeout=600,
        )
        if not isinstance(result, dict):
            raise VisualContractError(f"{model} returned invalid non-JSON metadata")
        download_provider_asset(_first_media_url(result, kind=kind), destination,
                                ".png" if kind == "image" else ".mp4")
        proof = {
            "model": model, "input_sha256": hashlib.sha256(
                json.dumps(payload, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "file_sha256": sha_file(destination),
            "review_status": "UNREVIEWED",
            "publishing_authorized": False,
        }
        destination.with_suffix(destination.suffix + ".provenance.json").write_text(
            json.dumps(proof, indent=2) + "\n", encoding="utf-8"
        )
        return proof

    def upload_image(self, path: Path) -> str:
        if not path.is_file() or path.stat().st_size < 2048:
            raise VisualContractError(f"missing generated image: {path}")
        return self.fal.upload_file(str(path))


def reference_prompt(role: str, description: str) -> str:
    category = "canonical character" if role in {"max","ada","old","zombie","biscuit"} else "canonical recurring prop"
    return (
        f"ONE ONLY original {category} identity sheet: {description}. "
        "High-end photorealistic cinematic survival drama, realistic anatomy, "
        "filmic lighting and natural surface textures. Consistent identifiable "
        "face/fur or vehicle shape from ALL views in future sequences. "
        "Centered full subject, plain deep slate backdrop, high clarity, "
        "single non-collage composition. No overlay text, watermark, logo, "
        "toy figures, game HUD, vector drawing, plastic skin, or cartoon."
    )


def shot_frame_prompt(shot: dict) -> str:
    return (
        "Create ONE ORIGINAL vertical 9:16 photorealistic film frame. "
        "Treat supplied reference images as EXACT canonical identities: same "
        "face, hair, adult anatomy, clothing, dog, steel-blue sedan, station "
        "geometry and materials. No redesign. IMPORTANT on-screen action: "
        + str(shot["physical_direction"]) + ". Narration: "
        + str(shot["narration"]) + ". Place: "
        + str(shot["location"]).replace("_", " ") + ". "
        "Central 70% of portrait screen contains the real actors/props and "
        "physical action, not vast empty sky. Sophisticated teal moonlight "
        "and warm amber practical lamps, realistic exposure, natural skin "
        "tones, 35mm photography, filmic contrast, readable scene depth. "
        "Do NOT add captions, letterforms, titles, subtitle, watermark, "
        "robotic figures, anime, comic art, extra cars, or extra people."
    )


def video_motion_prompt(shot: dict) -> str:
    return (
        "Cinematic single continuous photorealistic live-action shot. "
        "Physically visible chronological motion: " +
        str(shot["physical_direction"]) + ". "
        "Preserve the exact source-image face, clothes, same car geometry, "
        "location and dog anatomy across every frame. Show the actual "
        "narrated action clearly; no still-frame zoom, floating actors, "
        "jump cuts, morphing hands, teleported props or static slideshow. "
        "Controlled camera motion, tactile road movement, natural headlight "
        "and flashlight physics. Deep slate shadows and amber practical lights. "
        "No captions, UI, overlay, text, or music."
    )


def choose_video_duration(real_voice_seconds: float) -> int:
    """Provider permits exactly 6, 8 or 10 seconds; audio already measured."""
    if real_voice_seconds <= 0:
        raise VisualContractError("empty narrated scene cannot generate video")
    for seconds in (6, 8, 10):
        if real_voice_seconds <= seconds - 0.1:
            return seconds
    raise VisualContractError(
        f"narration lasts {real_voice_seconds:.2f}s, longer than 10s provider limit; "
        "split the physical action into separate authored shots"
    )


def _require_portrait_png(path: Path, *, reference: bool = False) -> None:
    try:
        with Image.open(path) as img:
            w, h = img.size
            if img.format != "PNG":
                raise VisualContractError("reference/frame must be a real PNG")
            img.verify()
    except (OSError, ValueError) as exc:
        raise VisualContractError(f"invalid image generated: {path}") from exc
    if w < 512 or h < 512:
        raise VisualContractError(f"AI image too small: {w}x{h}")
    if not reference and abs(w / h - 9 / 16) > 0.06:
        raise VisualContractError(f"first-frame image not portrait 9:16: {w}x{h}")


def generate_refs(provider: FalInference, roles: list[str], output: Path) -> dict:
    bibles = identity_bibles()
    references = {}
    for role in roles:
        destination = output / "references" / f"{role}.png"
        provider.generate(
            IMAGE_MODEL,
            {
                "prompt": reference_prompt(role, bibles[role]["visual_identity"]),
                "image_size": "square_hd", "output_format": "png",
            },
            kind="image", destination=destination,
        )
        _require_portrait_png(destination, reference=True)
        references[role] = provider.upload_image(destination)
    return references


def prepare_timeline(ep: dict, cfg: dict, *, work: Path):
    """Get real spoken audio and exact durations BEFORE paying for GPU clips."""
    import animate
    import render
    work.mkdir(parents=True, exist_ok=True)
    voices = render.synthesize_voices(cfg, ep, work)
    shots, total, lead = animate.build_timeline(ep, cfg, voices)
    if any(s.kind != "line" for s in shots):
        raise VisualContractError(
            "cloud preview requires narration-only timeline; video cards must "
            "be rendered in a separate approved stage"
        )
    for shot in shots:
        choose_video_duration(shot.dur)
    outro = max(0.0, total - lead - sum(v["dur"] for v in voices))
    audio = render.build_master_audio(voices, lead, outro, work, total, cfg)
    return shots, voices, total, audio


def generate_one(provider: FalInference, shot: dict, references: dict,
                 requested_duration: int, output: Path) -> dict:
    index = int(shot["index"])
    image = output / "frames" / f"{index:02d}.png"
    movie = output / "clips" / f"{index:02d}.mp4"
    identity_roles = {
        c["id"] for c in shot.get("characters", [])
    } | {p["id"] for p in shot.get("prop_references", [])}
    if not identity_roles:
        # A frame without a physical source still needs an environment visual.
        identity_roles = {"station" if "station" in shot["location"] else "sedan"}
    urls = [references[role] for role in sorted(identity_roles)]
    provider.generate(
        EDIT_MODEL,
        {
            "prompt": shot_frame_prompt(shot), "image_urls": urls,
            "aspect_ratio": "9:16", "resolution": "1K",
            "output_format": "png", "num_images": 1,
        },
        kind="image", destination=image,
    )
    _require_portrait_png(image)
    image_url = provider.upload_image(image)
    provider.generate(
        VIDEO_MODEL,
        {
            "image_url": image_url,
            "prompt": video_motion_prompt(shot),
            "duration": requested_duration, "resolution": "1080p",
            "aspect_ratio": "9:16", "fps": 25,
            "generate_audio": False, "enable_safety_checker": True,
        },
        kind="video", destination=movie,
    )
    from render_cinematic import _probe_video
    video_info = _probe_video(movie)
    if video_info["duration"] < requested_duration - 0.8:
        raise VisualContractError("model generated a truncated/short video")
    if video_info["width"] < 720 or video_info["height"] < 1280:
        raise VisualContractError("model video resolution below 720x1280")
    return {
        "id": shot["id"], "image": str(image), "clip": str(movie),
        "image_sha256": sha_file(image), "video_sha256": sha_file(movie),
        "duration": video_info["duration"], "requested_seconds": requested_duration,
        "approval": "UNREVIEWED", "publishing_authorized": False,
    }


def assemble_draft(ep: dict, frames: list, voices: list,
                   total: float, audio: Path, output: Path) -> Path:
    """Draft-only assembly. Never calls the approval-gated publishing renderer."""
    from render_cinematic import build_subtitles, _probe_video
    segments_dir = WORK / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)
    fps = 25
    segments = []
    for index, (shot, source) in enumerate(frames):
        target = segments_dir / f"{index:02d}.mp4"
        source = Path(source)
        info = _probe_video(source)
        if info["duration"] + 0.035 < shot.dur:
            raise VisualContractError(
                f"scene {index} shorter than Edge TTS, cannot repeat footage"
            )
        run([
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-i",str(source),"-t",f"{shot.dur:.3f}",
            "-vf",f"scale=1080:1920:force_original_aspect_ratio=increase,"
                   f"crop=1080:1920,setsar=1,fps={fps}",
            "-an","-c:v","libx264","-preset","fast","-crf","19",
            "-pix_fmt","yuv420p",str(target)
        ])
        segments.append(target)
    concat = WORK / "concat.txt"
    concat.write_text(
        "".join(f"file '{path.as_posix()}'\n" for path in segments),
        encoding="utf-8",
    )
    captions = WORK / "captions.ass"
    build_subtitles([shot for shot,_ in frames], voices, captions)
    draft = output / "day1_UNREVIEWED_preview.mp4"
    draft.parent.mkdir(parents=True, exist_ok=True)
    filter_chain = (
        "eq=contrast=1.06:saturation=1.10:brightness=0.005,"
        f"ass={captions.as_posix()},"
        "drawbox=x=0:y=90:w=iw:h=72:color=black@0.56:t=fill,"
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        "text='DRAFT - NOT APPROVED':fontcolor=white:fontsize=36:"
        "x=(w-text_w)/2:y=105"
    )
    run([
        "ffmpeg","-y","-hide_banner","-loglevel","error",
        "-f","concat","-safe","0","-i",str(concat),
        "-i",str(audio),"-vf",filter_chain,
        "-c:v","libx264","-preset","fast","-crf","19",
        "-pix_fmt","yuv420p","-c:a","aac","-b:a","160k",
        "-movflags","+faststart","-shortest",str(draft),
    ])
    data = _probe_video(draft)
    if abs(data["duration"] - total) > 1.0:
        raise VisualContractError(
            f"preview timeline wrong; video {data['duration']:.2f}s "
            f"vs narration {total:.2f}s"
        )
    return draft


def write_metadata(ep: dict, manifest: dict, plan: dict, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    (output / "story.json").write_text(
        json.dumps(ep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output / "plan.json").write_text(
        json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output / "caption.txt").write_text(ep["caption"] + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["plan","references","shot","day1"],
                        default="plan")
    parser.add_argument("--shot", type=int, default=0)
    parser.add_argument("--authorize-charges", action="store_true")
    parser.add_argument("--max-billable-calls", type=int, default=DEFAULT_MAX_CALLS)
    args = parser.parse_args()
    if args.max_billable_calls <= 0:
        parser.error("max-billable-calls must be positive")
    ep = day1_episode()
    ep["title_card"] = False
    manifest = build_manifest(ep, allow_unimplemented=True)
    full = manifest["shots"]
    if args.mode == "shot":
        if not 0 <= args.shot < len(full):
            parser.error(f"shot must be 0..{len(full)-1}")
        selected = [full[args.shot]]
    else:
        selected = full
    roles = required_roles(selected)
    plan = preflight_plan(selected, max_calls=args.max_billable_calls)
    write_metadata(ep, manifest, plan, OUTPUT)
    print(json.dumps({"mode":args.mode,**plan},indent=2), flush=True)
    if args.mode == "plan":
        print("PLAN ONLY: no FAL_KEY needed, no billable request, no Instagram")
        return
    if not args.authorize_charges:
        raise SystemExit(
            "Paid GPU requests are disabled. A manual GitHub Action input "
            "must explicitly authorize provider charges."
        )
    if not os.environ.get("FAL_KEY", "").strip():
        raise SystemExit(
            "Missing FAL_KEY GitHub Actions secret; no model request made."
        )
    cfg = load_config()
    cfg = dict(cfg)
    cfg["publishing_enabled"] = False
    cfg["cinematic_release_approved"] = False
    cfg["visual_mode"] = "cinematic_assets"
    cfg["render"] = dict(cfg.get("render") or {})
    cfg["render"]["title_card_seconds"] = 0
    if args.mode in {"shot","day1"}:
        shots, voices, total, audio = prepare_timeline(ep,cfg,work=WORK)
    provider = FalInference()
    refs = generate_refs(provider,roles,OUTPUT)
    if args.mode == "references":
        print("REFERENCES GENERATED; unreviewed. No videos, no posting.")
        return
    results = []
    for shot in selected:
        index = int(shot["index"])
        result = generate_one(
            provider,shot,refs,choose_video_duration(shots[index].dur),OUTPUT
        )
        results.append(result)
        print(f"[cloud] generated {shot['id']}, NOT approved", flush=True)
    (OUTPUT / "generated_shots.json").write_text(
        json.dumps(results,indent=2)+"\n", encoding="utf-8"
    )
    if args.mode == "day1":
        files = [(shot, OUTPUT / "clips" / f"{index:02d}.mp4")
                 for index,shot in enumerate(shots)]
        draft = assemble_draft(ep,files,voices,total,audio,OUTPUT)
        print(f"[cloud] finished UNREVIEWED Day 1 draft: {draft}",flush=True)
    else:
        print("One UNREVIEWED shot candidate created; no Instagram post.")
    print("No approval, no state mutation, no Instagram API calls.")


if __name__ == "__main__":
    main()
