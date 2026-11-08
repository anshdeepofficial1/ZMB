"""Human cinematic shot review with immutable file-hash approval receipts.

An approval is valid ONLY for the exact clip bytes AND exact narration + shot
direction prompt. Replacing a clip or editing a line invalidates approval.
This CLI never uploads or posts to Instagram.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from visual_manifest import ROOT, build_manifest, day1_episode, VisualContractError


CHECKS = (
    "narration_matches_visible_action",
    "character_identity_and_wardrobe",
    "consistent_vehicle_and_props",
    "natural_physical_motion",
    "cinematic_quality_and_framing",
)


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def prompt_hash(shot: dict) -> str:
    return hashlib.sha256(shot["prompt"].encode("utf-8")).hexdigest()


def receipt_path(clip: Path) -> Path:
    return clip.with_suffix(".review.json")


def approve(shot: dict, *, reviewer: str, checks: list[str]) -> dict:
    """Called ONLY from an explicit manual review operation."""
    selected = set(checks)
    if not reviewer.strip():
        raise VisualContractError("a named human reviewer is mandatory")
    if selected != set(CHECKS):
        raise VisualContractError(
            f"approval must explicitly confirm each check: {', '.join(CHECKS)}"
        )
    clip = Path(shot["video_path"])
    if not clip.is_file() or clip.stat().st_size < 1024:
        raise VisualContractError("cannot approve a missing/empty cinematic MP4")
    record = {
        "schema": 1,
        "shot_id": shot["id"],
        "status": "approved",
        "reviewer": reviewer.strip(),
        "approved_at_utc": datetime.now(timezone.utc).isoformat(),
        "checks": {name: True for name in CHECKS},
        "video_sha256": file_hash(clip),
        "prompt_sha256": prompt_hash(shot),
    }
    out = receipt_path(clip)
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    return record


def verify(shot: dict) -> dict:
    clip = Path(shot["video_path"])
    receipt = receipt_path(clip)
    if not clip.is_file():
        raise VisualContractError(f"required cinematic video missing: {clip}")
    if not receipt.is_file():
        raise VisualContractError(f"no human review receipt for shot {shot['id']}")
    try:
        record = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise VisualContractError(f"review receipt unreadable: {receipt}") from exc
    if (record.get("status") != "approved"
            or record.get("shot_id") != shot["id"]
            or not str(record.get("reviewer", "")).strip()):
        raise VisualContractError(f"shot {shot['id']} review receipt is not approved")
    if record.get("checks") != {key: True for key in CHECKS}:
        raise VisualContractError(f"shot {shot['id']} is missing mandatory review checks")
    if record.get("video_sha256") != file_hash(clip):
        raise VisualContractError(f"shot {shot['id']} changed after human approval")
    if record.get("prompt_sha256") != prompt_hash(shot):
        raise VisualContractError(f"narration/story direction changed after shot {shot['id']} approval")
    return record


def verify_manifest(manifest: dict) -> dict:
    shots = manifest.get("shots") or []
    if not shots:
        raise VisualContractError("manifest has no shots to review")
    records = [verify(shot) for shot in shots]
    return {
        "approved": True,
        "approved_shots": len(records),
        "reviewed_by": sorted({r["reviewer"] for r in records}),
    }


def main():
    parser = argparse.ArgumentParser(description="Verify or manually approve Day 1 cinematic shots")
    parser.add_argument("--day1", action="store_true", required=True)
    parser.add_argument("--shot", type=int)
    parser.add_argument("--reviewer", default="")
    parser.add_argument("--confirm-all-checks", action="store_true",
                        help="Manually confirm all five review criteria after actually watching clip")
    parser.add_argument("--verify", action="store_true",
                        help="Verify all clips and immutable review receipts without changing anything")
    args = parser.parse_args()
    manifest = build_manifest(day1_episode(), allow_unimplemented=True)
    if args.verify:
        result = verify_manifest(manifest)
        print(json.dumps(result, indent=2))
        return
    if args.shot is None or not args.confirm_all_checks:
        parser.error("manual approval requires --shot INDEX --reviewer NAME --confirm-all-checks")
    if args.shot < 0 or args.shot >= len(manifest["shots"]):
        parser.error("shot index outside manifest")
    shot = manifest["shots"][args.shot]
    approved = approve(shot, reviewer=args.reviewer, checks=list(CHECKS))
    print(f"APPROVED EXACT CLIP {shot['id']}, sha256={approved['video_sha256'][:16]}")
    print("This marks ONE shot reviewed, not the episode ready or Instagram published.")


if __name__ == "__main__":
    main()
