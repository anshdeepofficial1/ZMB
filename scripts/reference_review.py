"""Approve one real, manually inspected ZMB reference with a SHA-bound receipt.

A generated reference candidate is not an approved canonical identity until
the owner checks its visible face, animal anatomy, clothing, vehicle/scene
geometry and licensing. Replaced reference bytes invalidate downstream work.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

from PIL import Image, UnidentifiedImageError

from visual_manifest import ROOT, VisualContractError


def checksum(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def receipt_path(path: Path) -> Path:
    return path.with_suffix(".reference.json")


def valid_png(path: Path) -> tuple[int,int]:
    try:
        with Image.open(path) as image:
            if image.format != "PNG":
                raise VisualContractError(f"reference must be a real PNG: {path}")
            width,height=image.size
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise VisualContractError(f"invalid reference image: {path}") from exc
    if width < 512 or height < 512:
        raise VisualContractError(
            f"reference must be at least 512x512; got {width}x{height}: {path}"
        )
    return width,height


def approve_candidate(
    role: str, candidate: Path, identity: dict, *,
    reviewer: str, manually_inspected: bool=False, replace: bool=False,
) -> dict:
    if not manually_inspected or not reviewer.strip():
        raise VisualContractError("real visual inspection and a named human reviewer required")
    canonical=(ROOT / identity["reference"]).resolve()
    candidates=(ROOT/"out"/"reference_candidates"/role).resolve()
    source=candidate.resolve()
    if not source.is_relative_to(candidates):
        raise VisualContractError("reference approval must use a staged candidate for this exact role")
    if not source.is_file():
        raise VisualContractError(f"generated reference candidate missing: {source}")
    width,height=valid_png(source)
    if canonical.exists() and not replace:
        raise VisualContractError(
            f"approved canonical reference already exists: {canonical}; "
            "refuse overwrite without explicit --replace"
        )
    canonical.parent.mkdir(parents=True,exist_ok=True)
    temp=canonical.with_suffix(".png.partial")
    shutil.copyfile(source,temp)
    temp.replace(canonical)
    digest=checksum(canonical)
    receipt={
        "schema":1, "role":role, "status":"approved", "reviewer":reviewer.strip(),
        "approved_at_utc":datetime.now(timezone.utc).isoformat(),
        "file_sha256":digest,"width":width,"height":height,
        "identity_description_sha256":hashlib.sha256(
            identity["visual_identity"].encode("utf-8")
        ).hexdigest(),
        "source_candidate_sha256":checksum(source),
    }
    receipt_path(canonical).write_text(
        json.dumps(receipt,indent=2)+"\n",encoding="utf-8"
    )
    return receipt


def verify_reference(role: str, identity: dict, *, root: Path=ROOT) -> dict:
    path=(root / identity["reference"]).resolve()
    receipt_file=receipt_path(path)
    if not path.is_file():
        raise VisualContractError(f"Missing approved reference for {role}: {path}")
    valid_png(path)
    if not receipt_file.is_file():
        raise VisualContractError(f"Missing signed-off reference receipt for {role}: {receipt_file}")
    try:
        receipt=json.loads(receipt_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise VisualContractError(f"Unreadable reference approval for {role}") from exc
    if receipt.get("role") != role or receipt.get("status")!="approved" or not receipt.get("reviewer"):
        raise VisualContractError(f"Reference approval missing identity/reviewer for {role}")
    if receipt.get("file_sha256") != checksum(path):
        raise VisualContractError(f"Reference artwork changed since approval for {role}")
    expected=hashlib.sha256(identity["visual_identity"].encode("utf-8")).hexdigest()
    if receipt.get("identity_description_sha256") != expected:
        raise VisualContractError(f"Character/prop identity bible changed since approval for {role}")
    return receipt


def main():
    from reference_candidates import subjects
    parser=argparse.ArgumentParser()
    parser.add_argument("--role",required=True)
    parser.add_argument("--candidate",help="Candidate PNG from out/reference_candidates/ROLE/")
    parser.add_argument("--reviewer")
    parser.add_argument("--confirm-reviewed",action="store_true")
    parser.add_argument("--replace",action="store_true")
    parser.add_argument("--verify",action="store_true")
    args=parser.parse_args()
    identities=subjects()
    if args.role not in identities:
        parser.error(f"unknown role: {args.role}")
    if args.verify:
        record=verify_reference(args.role,identities[args.role])
        print(f"VERIFIED {args.role}: {record['file_sha256'][:16]}")
        return
    if not args.candidate or not args.reviewer or not args.confirm_reviewed:
        parser.error("--candidate, --reviewer and --confirm-reviewed required")
    record=approve_candidate(
        args.role,Path(args.candidate),identities[args.role],
        reviewer=args.reviewer,manually_inspected=True,replace=args.replace,
    )
    print(f"APPROVED {args.role}: {record['file_sha256'][:16]} "
          "— cinematic clips still require their own independent human review")


if __name__=="__main__":
    main()
