"""Review cinematic FIRST FRAME before image-to-video model animation.

Prohibits a random unrelated portrait, an old 2D cartoon still, altered
character face, or substituted car being passed automatically to LTX.
Approval is bound to the specific PNG bytes, screenplay direction, and all
approved canonical face/vehicle references. Still requires a real human eye.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from visual_manifest import (
    CAST_BIBLE, PROP_BIBLE, ROOT, VisualContractError,
    day1_episode, build_manifest,
)

CHECKS = (
    "professional_photorealistic_not_cartoon",
    "correct_character_face_anatomy_and_wardrobe",
    "exact_scene_action_and_all_required_props_visible",
    "correct_recurring_vehicle_and_location_geometry",
    "filmic_teal_amber_grade_and_central_phone_safe_composition",
)


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def digest_string(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def receipt_path(shot: dict) -> Path:
    return Path(shot["image_path"]).with_suffix(".frame.review.json")


def _expected(shot: dict) -> dict:
    from reference_review import verify_reference
    picture = Path(shot["image_path"])
    if not picture.is_file():
        raise VisualContractError(f"Missing scene FIRST FRAME PNG {picture}")
    try:
        with Image.open(picture) as image:
            w,h=image.size
            if image.format != "PNG":
                raise VisualContractError(f"Scene first frame must be PNG: {picture}")
            image.verify()
    except (OSError,UnidentifiedImageError,ValueError) as exc:
        raise VisualContractError(f"Invalid first-frame image: {picture}") from exc
    if w<512 or h<768 or abs(w/h-9/16)>0.05:
        raise VisualContractError("First frame is not a detailed 9:16 portrait source")
    cast=json.loads(CAST_BIBLE.read_text(encoding="utf-8"))
    props=json.loads(PROP_BIBLE.read_text(encoding="utf-8"))["props"]
    roles={c["id"] for c in shot.get("characters",[])}
    roles|={p["id"] for p in shot.get("prop_references",[])}
    references={}
    for role in sorted(roles):
        identity=cast.get(role) or props.get(role)
        if identity is None:
            raise VisualContractError(f"Unknown cinematic role: {role}")
        proof=verify_reference(role,identity,root=ROOT)
        references[role]=proof["file_sha256"]
    return {
        "shot_id":shot["id"],
        "png_sha256":digest_file(picture),
        "direction_sha256":digest_string(shot["physical_direction"]),
        "prompt_sha256":digest_string(shot["prompt"]),
        "canonical_references_sha256":digest_string(
            json.dumps(references,sort_keys=True)
        ),
        "width":w,"height":h,
    }


def approve_frame(shot: dict, *, reviewer: str, confirmed: dict) -> dict:
    if not reviewer.strip() or not all(confirmed.get(c) is True for c in CHECKS):
        raise VisualContractError(
            "Human editor must check ALL five criteria and supply reviewer name"
        )
    record={
        "schema":1,"status":"approved","reviewer":reviewer.strip(),
        "time_utc":datetime.now(timezone.utc).isoformat(),
        **_expected(shot),
        "checks":{key:True for key in CHECKS},
        "publishing_authorized":False,
    }
    path=receipt_path(shot)
    path.write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
    return record


def verify_frame(shot: dict) -> dict:
    path=receipt_path(shot)
    if not path.is_file():
        raise VisualContractError(
            f"First-frame human approval missing for {shot['id']}: {path}"
        )
    try:
        actual=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError) as exc:
        raise VisualContractError(f"Invalid first-frame review receipt: {path}") from exc
    required=_expected(shot)
    for field,value in required.items():
        if actual.get(field)!=value:
            raise VisualContractError(
                f"First-frame approval invalidated by changed {field}: {shot['id']}"
            )
    if (actual.get("status")!="approved" or not actual.get("reviewer")
            or not all((actual.get("checks") or {}).get(c) is True for c in CHECKS)):
        raise VisualContractError(
            f"First-frame receipt is not an actual checked human approval: {shot['id']}"
        )
    return actual


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--day1",action="store_true",required=True)
    parser.add_argument("--shot",type=int,required=True)
    parser.add_argument("--reviewer",default="")
    parser.add_argument("--confirm-all-checks",action="store_true")
    parser.add_argument("--verify",action="store_true")
    args=parser.parse_args()
    shots=build_manifest(day1_episode(),allow_unimplemented=True)["shots"]
    if not 0<=args.shot<len(shots):
        parser.error(f"--shot must be between 0 and {len(shots)-1}")
    shot=shots[args.shot]
    if args.verify:
        proof=verify_frame(shot)
        print(f"FIRST FRAME VERIFIED: {proof['shot_id']}")
    else:
        if not args.confirm_all_checks:
            parser.error("you must visually inspect the actual frame and explicitly confirm all checks")
        proof=approve_frame(shot,reviewer=args.reviewer,
                            confirmed={key:True for key in CHECKS})
        print(f"FIRST FRAME APPROVED FOR ANIMATION ONLY: {proof['shot_id']}")


if __name__=="__main__":
    main()
