"""Generate ORIGINAL scene-specific stills and video using YOUR ComfyUI GPU.

ComfyUI workflows are API-format JSON, not drag-and-drop UI format.
No paid cloud inference or public posting happens here.

Example:
 python scripts/comfyui_cinematic.py --day1 --server http://127.0.0.1:8188 \
     --bindings workflows/zmb/bindings.json --shot 0

A valid bindings file and installed compatible model workflows are required.
All outputs remain UNREVIEWED until independently inspected.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import time
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import requests

from visual_manifest import (
    ROOT, CINEMATIC_ROOT, CAST_BIBLE, PROP_BIBLE, build_manifest, day1_episode,
    VisualContractError,
)


def load_bindings(path: Path, *, require_video: bool = True) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    for stage in (("image", "video") if require_video else ("image",)):
        item = data.get(stage)
        if not isinstance(item, dict):
            raise VisualContractError(f"bindings missing '{stage}' stage")
        for key in ("workflow_file", "prompt", "output_node"):
            if not item.get(key):
                raise VisualContractError(f"bindings stage '{stage}' missing {key}")
        if stage == "video" and not item.get("source_image"):
            raise VisualContractError("video stage must use the actual approved/generated image as its first frame")
    return data


def set_input(workflow: dict, binding: list, value: Any) -> None:
    if not isinstance(binding, list) or len(binding) != 2:
        raise VisualContractError(f"node binding must be [node_id, input], got {binding!r}")
    node_id, input_key = str(binding[0]), str(binding[1])
    inputs = workflow.get(node_id, {}).get("inputs")
    if not isinstance(inputs, dict) or input_key not in inputs:
        raise VisualContractError(
            f"ComfyUI API workflow missing node/input {node_id}.{input_key}"
        )
    inputs[input_key] = value


def prepare_workflow(stage: dict, *, prompt: str, image: str | None = None,
                     references: dict[str, str] | None = None) -> dict:
    template_path = ROOT / stage["workflow_file"]
    if not template_path.is_file():
        raise VisualContractError(f"ComfyUI API workflow missing: {template_path}")
    workflow = copy.deepcopy(json.loads(template_path.read_text(encoding="utf-8")))
    if not isinstance(workflow, dict) or "nodes" in workflow:
        raise VisualContractError(
            "Expected exported API workflow: dict of node IDs, not ComfyUI UI-format JSON"
        )
    set_input(workflow, stage["prompt"], prompt)
    if stage.get("negative_prompt"):
        set_input(workflow, stage["negative_prompt"],
                  "bad anatomy, identity changes, duplicate limbs, morphing car, "
                  "wrong wardrobe, text overlay, cartoon cutout, flicker, inconsistent geometry")
    if image is not None:
        if not stage.get("source_image"):
            raise VisualContractError("video workflow has no bound source image node")
        set_input(workflow, stage["source_image"], image)
    for role, filename in (references or {}).items():
        bindings = stage.get("reference_nodes") or {}
        if role not in bindings:
            raise VisualContractError(
                f"workflow lacks reference conditioning input for '{role}'"
            )
        set_input(workflow, bindings[role], filename)
    if stage.get("seed"):
        set_input(workflow, stage["seed"], int(hashlib.sha256(
            prompt.encode("utf-8")).hexdigest()[:8], 16))
    return workflow


def select_output(record: dict, node_id: str, suffix: str) -> dict:
    node = (record.get("outputs") or {}).get(str(node_id), {})
    pools = ("images",) if suffix == ".png" else ("videos", "gifs", "video")
    for key in pools:
        items = node.get(key, [])
        if isinstance(items, dict):
            items = [items]
        for item in items:
            if isinstance(item, dict) and str(item.get("filename", "")).lower().endswith(suffix):
                if item.get("type", "output") != "output":
                    continue
                return item
    raise VisualContractError(
        f"ComfyUI output node {node_id} has no output {suffix}; "
        "check SaveImage/SaveVideo node and output format"
    )


class ComfyClient:
    def __init__(self, base_url: str, *, token: str = "", timeout: float = 60):
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise VisualContractError("ComfyUI server URL must be an http(s) address")
        self.base_url = base_url.rstrip("/")
        self.http = requests.Session()
        if token:
            self.http.headers.update({"Authorization": f"Bearer {token}"})
        self.timeout = timeout

    def _json(self, method: str, path: str, **kwargs) -> dict:
        res = self.http.request(method, self.base_url + path, timeout=self.timeout, **kwargs)
        res.raise_for_status()
        data = res.json()
        if not isinstance(data, dict):
            raise VisualContractError(f"invalid ComfyUI response to {path}")
        return data

    def health(self):
        self._json("GET", "/system_stats")

    def upload_image(self, path: Path) -> str:
        if not path.is_file() or path.stat().st_size < 100:
            raise VisualContractError(f"character/still image is absent or empty: {path}")
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with path.open("rb") as fp:
            data = self._json(
                "POST", "/upload/image",
                files={"image": (path.name, fp, mime)},
                data={"overwrite": "false"},
            )
        name = data.get("name")
        if not isinstance(name, str) or not name:
            raise VisualContractError("ComfyUI upload returned no image name")
        return name

    def execute(self, workflow: dict, *, timeout_s: int = 1800) -> dict:
        enqueued = self._json(
            "POST", "/prompt",
            json={"prompt": workflow, "client_id": str(uuid4())},
        )
        prompt_id = enqueued.get("prompt_id")
        if not isinstance(prompt_id, str):
            raise VisualContractError(
                f"ComfyUI rejected workflow: {str(enqueued.get('node_errors'))[:500]}"
            )
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            result = self._json("GET", "/history/" + prompt_id)
            entry = result.get(prompt_id)
            if isinstance(entry, dict):
                status = entry.get("status") or {}
                if status.get("status_str") == "error":
                    raise VisualContractError(
                        f"ComfyUI generation failed for {prompt_id}: "
                        f"{str(status.get('messages'))[:400]}"
                    )
                if status.get("completed") is True and entry.get("outputs"):
                    return entry
            time.sleep(5)
        raise VisualContractError(f"ComfyUI job {prompt_id} exceeded timeout; no output approved")

    def download(self, descriptor: dict, dest: Path, *, max_bytes: int = 2_000_000_000) -> None:
        params = {
            "filename": descriptor["filename"],
            "subfolder": descriptor.get("subfolder", ""),
            "type": descriptor.get("type", "output"),
        }
        dest.parent.mkdir(parents=True, exist_ok=True)
        temp = dest.with_suffix(dest.suffix + ".partial")
        total = 0
        try:
            with self.http.get(
                self.base_url + "/view", params=params,
                stream=True, timeout=self.timeout,
            ) as res:
                res.raise_for_status()
                with temp.open("wb") as fp:
                    for chunk in res.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            total += len(chunk)
                            if total > max_bytes:
                                raise VisualContractError("ComfyUI output exceeds maximum expected file size")
                            fp.write(chunk)
            if total < 1024:
                raise VisualContractError(f"ComfyUI returned empty or tiny file for {dest}")
            if dest.suffix == ".png" and temp.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
                raise VisualContractError(f"ComfyUI returned invalid PNG: {dest}")
            if dest.suffix == ".mp4" and b"ftyp" not in temp.read_bytes()[:64]:
                raise VisualContractError(f"ComfyUI returned invalid MP4: {dest}")
            temp.replace(dest)
        finally:
            temp.unlink(missing_ok=True)


def sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def validate_generation_preflight(shots: list, bindings: dict, cast: dict, props: dict, *, require_video: bool = True) -> None:
    """Fail BEFORE GPU job submission unless every required reference is approved."""
    from reference_review import verify_reference
    stages = ("image", "video") if require_video else ("image",)
    for stage_name in stages:
        stage = bindings[stage_name]
        flow = ROOT / stage["workflow_file"]
        if not flow.is_file():
            raise VisualContractError(f"Required {stage_name} API workflow missing: {flow}")
        workflow = json.loads(flow.read_text(encoding="utf-8"))
        set_input(workflow, stage["prompt"], "preflight-test")
        if stage_name == "video":
            set_input(workflow, stage["source_image"], "preflight-test.png")
    for shot in shots:
        required = {person["id"] for person in shot["characters"]}
        required |= {asset["id"] for asset in shot.get("prop_references", [])}
        for role in required:
            identity = cast.get(role) or props.get(role)
            if not identity:
                raise VisualContractError(f"Missing identity record: {role}")
            # A PNG file alone is not an approved identity. Both image bytes
            # and the identity definition must match the review receipt.
            verify_reference(role, identity, root=ROOT)
            for stage_name in stages:
                spec = bindings[stage_name]
                if role not in (spec.get("reference_nodes") or {}):
                    raise VisualContractError(
                        f"{stage_name} workflow does not condition on {role}"
                    )
                wf = json.loads((ROOT / spec["workflow_file"]).read_text(encoding="utf-8"))
                set_input(wf, spec["reference_nodes"][role], "preflight-test.png")


def generate_shot(
    client: ComfyClient, shot: dict, bindings: dict, cast: dict, props: dict,
    *, resume: bool = False, image_only: bool = False,
) -> dict:
    still = Path(shot["image_path"])
    video = Path(shot["video_path"])
    # Explicit reference conditioning is required for every character.
    references = {}
    from reference_review import verify_reference
    for character in shot["characters"]:
        role = character["id"]
        reference = ROOT / cast[role]["reference"]
        verify_reference(role, cast[role], root=ROOT)
        if role not in references:
            if not reference.is_file():
                raise VisualContractError(
                    f"Missing approved {role} reference image: {reference}. "
                    "Create and manually approve identities before generation."
                )
            references[role] = client.upload_image(reference)
    for prop in shot.get("prop_references", []):
        role = prop["id"]
        if role in references:
            continue
        reference = ROOT / props[role]["reference"]
        verify_reference(role, props[role], root=ROOT)
        if not reference.is_file():
            raise VisualContractError(
                f"Missing approved recurring prop {role} reference: {reference}"
            )
        references[role] = client.upload_image(reference)
    if not (resume and still.is_file() and still.stat().st_size > 1024):
        image_cfg = bindings["image"]
        image_flow = prepare_workflow(
            image_cfg, prompt=shot["prompt"], references=references
        )
        image_run = client.execute(image_flow)
        image_out = select_output(image_run, image_cfg["output_node"], ".png")
        client.download(image_out, still)
    if image_only:
        # LTX-Video requires a real scene-specific first frame. Generate one
        # with approved identities; never substitute a generic cast portrait.
        proof = {
            "shot_id": shot["id"], "source_image": str(still),
            "image_sha256": sha256(still), "approval": "UNREVIEWED",
            "publishing_authorized": False,
        }
        still.with_suffix(".frame.provenance.json").write_text(
            json.dumps(proof, indent=2) + "\n", encoding="utf-8"
        )
        return proof
    if not (resume and video.is_file() and video.stat().st_size > 1024):
        remote_still = client.upload_image(still)
        video_cfg = bindings["video"]
        motion = (
            shot["physical_direction"]
            + " Actual motion follows real physics, objects keep identity and "
              "shape across every frame; deliberate cinematic camera movement. "
              "No freezes or still-image zoom substitutes. "
            + shot["prompt"]
        )
        video_flow = prepare_workflow(
            video_cfg, prompt=motion, image=remote_still, references=references
        )
        video_run = client.execute(video_flow)
        video_out = select_output(video_run, video_cfg["output_node"], ".mp4")
        client.download(video_out, video)
    provenance = {
        "shot_id": shot["id"],
        "narration": shot["narration"],
        "direction": shot["physical_direction"],
        "required_props": shot["required_props"],
        "image_sha256": sha256(still),
        "video_sha256": sha256(video),
        "approval": "UNREVIEWED",
        "publishing_authorized": False,
        "workflow_bindings_sha256": hashlib.sha256(
            json.dumps(bindings, sort_keys=True).encode("utf-8")).hexdigest(),
    }
    sidecar = video.with_suffix(".provenance.json")
    sidecar.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return provenance


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--day1", action="store_true", required=True)
    parser.add_argument("--server", default=os.environ.get("ZMB_COMFYUI_URL", ""))
    parser.add_argument("--token-env", default="ZMB_COMFYUI_TOKEN")
    parser.add_argument("--bindings", default="workflows/zmb/bindings.json")
    parser.add_argument("--shot", type=int, help="Zero-based shot to generate (omit for all)")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--image-only", action="store_true",
                        help="Generate first-frame PNGs for the internal LTX model; no video stage")
    parser.add_argument("--dry-run", action="store_true", help="Validate prompts only, never contact the server")
    args = parser.parse_args()
    manifest = build_manifest(day1_episode(), allow_unimplemented=True)
    shots = manifest["shots"]
    if args.shot is not None:
        if args.shot < 0 or args.shot >= len(shots):
            parser.error(f"shot must be in range 0..{len(shots)-1}")
        shots = [shots[args.shot]]
    for shot in shots:
        print(f"{shot['id']}: {shot['physical_direction']}")
    if args.dry_run:
        print("DRY RUN: no ComfyUI contact, no generated files, no Instagram publishing")
        return
    bindings = load_bindings(ROOT / args.bindings, require_video=not args.image_only)
    if not args.server:
        parser.error("--server or ZMB_COMFYUI_URL required for real generation")
    cast = json.loads(CAST_BIBLE.read_text(encoding="utf-8"))
    props = json.loads(PROP_BIBLE.read_text(encoding="utf-8"))["props"]
    validate_generation_preflight(shots, bindings, cast, props, require_video=not args.image_only)
    client = ComfyClient(args.server, token=os.environ.get(args.token_env, ""))
    client.health()
    for shot in shots:
        result = generate_shot(
            client, shot, bindings, cast, props,
            resume=args.resume, image_only=args.image_only
        )
        if args.image_only:
            print(f"FIRST FRAME, NOT REVIEWED: {result['shot_id']} "
                  f"png sha256={result['image_sha256'][:16]}")
        else:
            print(f"GENERATED, NOT REVIEWED: {result['shot_id']} "
                  f"mp4 sha256={result['video_sha256'][:16]}")
    print("Assets generated, but publishing remains BLOCKED until every clip is reviewed.")


if __name__ == "__main__":
    main()
