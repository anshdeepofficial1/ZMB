"""Report all authored narration without a verifiable physical visual beat.

The current channel must remain paused while incomplete nodes exist. This tool
reports incompleteness instead of declaring a synthetic '100% ready' result.
"""
from __future__ import annotations

import json
from pathlib import Path
from visual_manifest import STORY, DIRECTIONS, CINEMATIC_ROOT, IMPLEMENTED_VECTOR_BEATS


def scan() -> list[dict]:
    scn = json.loads(STORY.read_text(encoding="utf-8"))
    missing = []
    for arc_id, arc in scn["arcs"].items():
        for node_id, node in arc["nodes"].items():
            for index, line in enumerate(node.get("lines") or []):
                shot = line.get("shot") or {}
                beat = shot.get("beat")
                if beat not in IMPLEMENTED_VECTOR_BEATS:
                    missing.append({
                        "arc": arc_id,
                        "node": node_id,
                        "line": index,
                        "narration": line.get("text", ""),
                        "beat": beat,
                        "reason": "no explicit implemented visual beat",
                    })
    return missing


if __name__ == "__main__":
    scene = json.loads(STORY.read_text(encoding="utf-8"))["arcs"]
    directions = json.loads(DIRECTIONS.read_text(encoding="utf-8"))["arcs"]
    missing_direction = []
    missing_media = []
    total = 0
    for arc, arc_data in scene.items():
        for node, data in arc_data["nodes"].items():
            lines = data.get("lines") or []
            refs = directions.get(arc, {}).get(node, [])
            if len(refs) != len(lines):
                missing_direction.append(f"{arc}/{node}: direction count mismatch")
                continue
            for index, ref in enumerate(refs):
                total += 1
                if not ref.get("action") or not ref.get("props"):
                    missing_direction.append(f"{arc}/{node}/{index}")
                clip = CINEMATIC_ROOT / arc / node / f"{index:02d}.mp4"
                if not clip.is_file():
                    missing_media.append(str(clip.relative_to(CINEMATIC_ROOT)))
    unmapped_vector = scan()
    print(f"Directed spoken shots: {total}")
    print(f"Missing physical directions: {len(missing_direction)}")
    print(f"Missing real cinematic MP4 clips: {len(missing_media)}")
    print(f"Shots without verified vector action renderer: {len(unmapped_vector)}")
    if missing_direction or missing_media:
        print("NOT READY: Cinematic release remains blocked")
        raise SystemExit(1)
    print("All lines have media files; still require human footage review")

