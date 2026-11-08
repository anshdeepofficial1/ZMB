"""Shot-by-shot source of truth for cinematic footage.

This is intentionally fail-closed: no generated footage is substituted with
unrelated stock scenes, and a line without a visual action cannot be approved.
Run: python scripts/visual_manifest.py --day1
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CAST_BIBLE = ROOT / "content" / "cast_bible.json"
STORY = ROOT / "content" / "scenarios.json"
DIRECTIONS = ROOT / "content" / "shot_directions.json"
PROP_BIBLE = ROOT / "content" / "prop_bible.json"
CINEMATIC_ROOT = ROOT / "assets" / "cinematic"

# Each supported visual event has a concrete renderer or separately generated
# clip. Other narration lines need a storyboard BEFORE any production release.
IMPLEMENTED_VECTOR_BEATS = {
    "car_driving", "engine_stall", "car_interior", "flashlight_exit",
    "spot_station", "door_shadow", "door_handle", "breakdown",
    "backpack_exit", "choice_teaser",
}

VISUAL_OBLIGATIONS = (
    (("drives", "driving", "drive through"), {"car_driving", "car_interior"}),
    (("engine", "jerks to a stop", "stalls"), {"engine_stall", "breakdown", "car_interior"}),
    (("headlights",), {"car_driving", "engine_stall"}),
    (("dashboard", "turns the key"), {"car_interior"}),
    (("flashlight",), {"flashlight_exit"}),
    (("shadow", "locked glass door"), {"door_shadow", "door_handle"}),
    (("knocks", "door handle"), {"door_handle"}),
)


class VisualContractError(ValueError):
    """Story direction is insufficient to render the spoken action faithfully."""


def _characters(shot: dict, bible: dict) -> list[dict]:
    cast = []
    for role, action in shot.get("cast", []):
        if role not in bible:
            raise VisualContractError(f"unknown character '{role}'")
        cast.append({
            "id": role, "action": action, "identity": bible[role]["visual_identity"],
            "reference": bible[role]["reference"],
        })
    return cast


def _validate_line(index: int, line: dict, allow_unimplemented: bool, direction: dict | None = None):
    text = str(line.get("text") or "").strip()
    shot = line.get("shot") or {}
    beat = str(shot.get("beat") or "").strip()
    if not text or not shot.get("place"):
        raise VisualContractError(f"line {index}: missing narration or location")
    has_directed_asset = bool(
        allow_unimplemented and direction
        and len(str(direction.get("action", "")).strip()) >= 15
        and direction.get("props")
    )
    if not beat and not has_directed_asset:
        raise VisualContractError(
            f"line {index}: no physical action/visual beat for '{text[:75]}'"
        )
    if not allow_unimplemented and beat not in IMPLEMENTED_VECTOR_BEATS:
        raise VisualContractError(
            f"line {index}: visual beat '{beat}' has no verified vector renderer"
        )
    if has_directed_asset:
        # External cinematic assets can depict actions not supported by SVG.
        # Required props are included in the shot prompt and reviewed on film.
        return
    lowered = text.lower()
    for triggers, valid_beats in VISUAL_OBLIGATIONS:
        if any(term in lowered for term in triggers) and beat not in valid_beats:
            raise VisualContractError(
                f"line {index}: spoken entity/action {triggers} is not visibly "
                f"represented by beat '{beat}'"
            )


def build_manifest(
    episode: dict[str, Any], *, allow_unimplemented: bool = False
) -> dict[str, Any]:
    bible = json.loads(CAST_BIBLE.read_text(encoding="utf-8"))
    prop_bible = json.loads(PROP_BIBLE.read_text(encoding="utf-8"))["props"]
    directions = json.loads(DIRECTIONS.read_text(encoding="utf-8"))["arcs"]
    node_directions = directions.get(episode["arc"], {}).get(episode["node"], [])
    if len(node_directions) != len(episode.get("lines") or []):
        raise VisualContractError("shot direction count differs from spoken lines")
    manifest_shots = []
    for index, line in enumerate(episode.get("lines") or []):
        direction = node_directions[index]
        _validate_line(index, line, allow_unimplemented, direction)
        meta = line["shot"]
        shot_id = f"s{episode['season']}_d{int(episode['day']):03d}_{index:02d}"
        characters = _characters(meta, bible)
        action = str(direction.get("action", "")).strip()
        props = direction.get("props") or []
        if not action or not props:
            raise VisualContractError(f"line {index}: physical direction missing")
        beat = str(meta.get("beat") or "cinematic_asset_only")
        place = meta["place"].replace("_", " ")
        text = line["text"]
        # Recurring environments and vehicles must use the SAME approved
        # reference image in every scene, including car interiors.
        scene_words = " ".join([text, action, *props]).lower()
        prop_references = []
        for prop_id, identity in prop_bible.items():
            keywords = identity.get("detection_keywords", [])
            if any(re.search(r"\b" + re.escape(word.lower()) + r"\b", scene_words)
                   for word in keywords):
                prop_references.append({
                    "id": prop_id,
                    "identity": identity["visual_identity"],
                    "reference": identity["reference"],
                })
        prompt = (
            "9:16 cinematic stylized 3D animated survival thriller, professional "
            "film lighting, tactile surfaces, anatomically plausible characters, "
            "physically consistent environment, clear foreground action, "
            "true depth of field; NO flat cartoon or text baked into image. "
            f"LOCATION: {place}; TIME: {meta.get('time','night')}; "
            f"MOOD: {meta.get('mood','tense')}. "
            f"VISIBLE PHYSICAL ACTION: {action}. "
            f"REQUIRED PHYSICAL PROPS: {', '.join(props)}. "
            f"SHOT MUST DEPICT THIS EXACT NARRATED EVENT: {text} "
            "Camera is deliberately staged so all mentioned objects and the "
            "subject's interaction with them are visible. "
            f"CAMERA: {meta.get('cam','push')}. "
            + " ".join(
                f"CHARACTER {item['id']}: {item['identity']}; "
                f"ACTION: {item['action']}."
                for item in characters
            )
            + " ".join(
                f"RECURRING PROP {asset['id']}: {asset['identity']}"
                for asset in prop_references
            )
            + " No extra characters, no objects teleporting or changing state, "
            "consistent vehicle body and color in all angles, no captions, "
            "no watermarks, no invented dialogue."
        )
        manifest_shots.append({
            "id": shot_id, "index": index, "narration": text,
            "location": meta["place"], "beat": beat,
            "physical_direction": action, "required_props": props,
            "reviewed": bool(direction.get("reviewed", False)),
            "camera": meta.get("cam", "push"),
            "fx": meta.get("fx", "none"),
            "characters": characters,
            "prop_references": prop_references,
            "prompt": prompt,
            "video_path": str(
                CINEMATIC_ROOT / episode["arc"] / episode["node"]
                / f"{index:02d}.mp4"
            ),
            "image_path": str(
                CINEMATIC_ROOT / episode["arc"] / episode["node"]
                / f"{index:02d}.png"
            ),
        })
    return {
        "schema": 1,
        "episode": {
            "season": episode["season"], "day": episode["day"],
            "arc": episode["arc"], "node": episode["node"]
        },
        "style": "consistent cinematic stylized 3D survival film",
        "shots": manifest_shots,
        "approval": {
            "required": [
                "one visual per spoken event",
                "stable character faces/outfits",
                "physically correct vehicle motion and props",
                "matching location, continuity, and lighting",
                "no scene substitutions",
                "every frame-to-voice match manually reviewed",
            ],
            "approved": bool(manifest_shots) and all(s["reviewed"] for s in manifest_shots),
        },
    }


def day1_episode() -> dict[str, Any]:
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import engine
    cfg = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    story = engine.load_scenarios()
    state = {
        "season": 1, "day": 0, "arc": "road", "node": "intro",
        "location": "the empty highway",
        "stats": dict(cfg.get("stats_reset", {})),
        "history": [], "last_episode": None, "recent_hashtags": [],
    }
    return engine.build_episode(state, story, cfg)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--day1", action="store_true", required=True,
                        help="Build the cinematic manifest for the Day 1 restart")
    parser.add_argument("--output", default="out/day1_visual_manifest.json")
    args = parser.parse_args()
    result = build_manifest(day1_episode())
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print(f"Visual contract validated: {len(result['shots'])} shots. "
          f"Manifest: {output}. Publishing remains paused.")


if __name__ == "__main__":
    main()
