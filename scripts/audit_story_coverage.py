"""Report all authored narration without a verifiable physical visual beat.

The current channel must remain paused while incomplete nodes exist. This tool
reports incompleteness instead of declaring a synthetic '100% ready' result.
"""
from __future__ import annotations

import json
from pathlib import Path
from visual_manifest import STORY, IMPLEMENTED_VECTOR_BEATS


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
    missing = scan()
    for row in missing:
        print(f"{row['arc']}/{row['node']} [{row['line']}]: "
              f"{row['narration'][:100]}")
    print(f"\nINCOMPLETE LINES: {len(missing)}")
    if missing:
        raise SystemExit(1)
    print("ALL NARRATION LINES HAVE VERIFIED VECTOR VISUAL BEATS")
