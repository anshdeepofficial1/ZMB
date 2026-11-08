"""Real reference-image bootstrap for first-time ZMB cinematic production.

Renders candidate original reference PNGs with an authorized ComfyUI image
model, without relying on nonexistent pre-approved references. Candidates
are NEVER automatically promoted to production reference assets.

Example:
  python scripts/reference_candidates.py --all --dry-run
  python scripts/reference_candidates.py --role max --server http://127.0.0.1:8188 \
      --bindings workflows/zmb/bindings.json --count 3
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from comfyui_cinematic import (
    ComfyClient, load_bindings, prepare_workflow, select_output,
)
from visual_manifest import CAST_BIBLE, PROP_BIBLE, ROOT, VisualContractError

CANDIDATES = ROOT / "out" / "reference_candidates"
STYLE = (
    "Original premium cinematic stylized 3D zombie survival game character/prop "
    "asset; realistic physically based materials, tactile textures, filmic "
    "lighting, clean consistent proportions, no vector cartoon, no low-poly "
    "rigging visible, no anime eyes, no logos, no lettering, no watermark, "
    "one clearly visible subject centered in frame, neutral muted studio "
    "background, full subject unobstructed and in sharp focus."
)


def subjects() -> dict[str, dict]:
    cast = json.loads(CAST_BIBLE.read_text(encoding="utf-8"))
    props = json.loads(PROP_BIBLE.read_text(encoding="utf-8"))["props"]
    both = dict(cast)
    both.update(props)
    return both


def reference_prompt(role: str, identity: dict, index: int) -> str:
    if index < 1:
        raise VisualContractError("candidate number must start at one")
    context = "character" if role in {"max", "biscuit", "ada", "old", "zombie"} else "environment/vehicle"
    return (
        f"{STYLE} SOURCE ID: {role}. TYPE: {context}. "
        f"VISUAL IDENTITY MUST MATCH: {identity['visual_identity']} "
        "Character: full body 3/4 front view, legs/feet visible, "
        "expressive natural human anatomy. If dog, full body canine anatomy. "
        "Vehicle: complete 3/4 side view and wheels clearly visible. "
        "Building: wide 3/4 view exposing recognizable signage and entrance. "
        f"Reference variation {index}: same original design, only subtle "
        "lighting and camera position may differ. No props that alter identity."
    )


def generate_candidates(client: ComfyClient, stage: dict, identities: dict,
                        roles: list[str], count: int) -> list[Path]:
    if not 1 <= count <= 8:
        raise VisualContractError("candidate count must be between 1 and 8")
    produced = []
    for role in roles:
        identity = identities[role]
        for i in range(1, count + 1):
            prompt = reference_prompt(role, identity, i)
            workflow = prepare_workflow(stage, prompt=prompt)
            result = client.execute(workflow)
            output = select_output(result, str(stage["output_node"]), ".png")
            destination = CANDIDATES / role / f"candidate_{i:02d}.png"
            client.download(output, destination)
            produced.append(destination)
            print(f"UNREVIEWED: {destination.relative_to(ROOT)}")
    return produced


def main():
    ap = argparse.ArgumentParser()
    target = ap.add_mutually_exclusive_group(required=True)
    target.add_argument("--role", help="One role ID from the bibles")
    target.add_argument("--all", action="store_true", help="Generate every role")
    ap.add_argument("--server", default=os.environ.get("ZMB_COMFYUI_URL", ""))
    ap.add_argument("--token-env", default="ZMB_COMFYUI_TOKEN")
    ap.add_argument("--bindings", default="workflows/zmb/bindings.json")
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    args=ap.parse_args()

    known = subjects()
    if args.role and args.role not in known:
        ap.error(f"Unknown role '{args.role}'. Choose from {', '.join(known)}")
    roles = list(known) if args.all else [args.role]
    if not 1 <= args.count <= 8:
        ap.error("--count must be 1..8")
    for role in roles:
        for i in range(1, args.count + 1):
            print(f"{role} candidate {i}: {reference_prompt(role, known[role], i)}")
    if args.dry_run:
        print("DRY RUN: no GPU used; no reference assets approved or Instagram posted")
        return
    if not args.server:
        ap.error("real generation requires --server or ZMB_COMFYUI_URL")
    bindings = load_bindings(ROOT / args.bindings)
    client = ComfyClient(args.server, token=os.environ.get(args.token_env, ""))
    client.health()
    generate_candidates(client, bindings["image"], known, roles, args.count)
    print("Candidates generated; select and approve real images individually BEFORE video generation.")


if __name__ == "__main__":
    main()
