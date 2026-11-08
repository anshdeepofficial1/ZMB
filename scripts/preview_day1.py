"""Isolated Day 1 cinematic reboot preview. NEVER modifies live state or posts.

Examples:
  python scripts/preview_day1.py --stills
  python scripts/preview_day1.py --video
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import OUT_DIR, load_config, log
from visual_manifest import build_manifest, day1_episode
import render


def preview(video: bool = False, stills: bool = False) -> dict:
    if not (video or stills):
        raise ValueError("select --video or --stills")
    cfg = load_config()
    cfg = dict(cfg)  # Do not mutate any actual config.
    cfg["visual_mode"] = "procedural"
    cfg["enforce_visual_contract"] = True
    cfg["publishing_enabled"] = False
    cfg["render"] = dict(cfg.get("render") or {})
    cfg["render"]["title_card_seconds"] = 0  # hook starts at frame 0
    ep = day1_episode()
    ep["title_card"] = False
    manifest = build_manifest(ep)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "day1_visual_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (OUT_DIR / "episode.json").write_text(
        json.dumps(ep, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (OUT_DIR / "caption.txt").write_text(ep["caption"] + "\n", encoding="utf-8")
    result = {"manifest": str(OUT_DIR / "day1_visual_manifest.json"), "shots": len(ep["lines"])}
    if stills:
        result["stills"] = render.render_stills(cfg, ep, Log=log)
    if video:
        result["video"] = render.render_episode(cfg, ep, Log=log)["video_path"]
    log("[preview] complete. Live state unchanged; no Instagram API touched.")
    return result


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--video", action="store_true")
    group.add_argument("--stills", action="store_true")
    options = parser.parse_args()
    result = preview(video=options.video, stills=options.stills)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
