"""Explicit isolated graphic-novel pilot. No publish, no state changes."""
import json
from pathlib import Path
import animate
import graphic_novel as art
import preview_day1

if __name__ == "__main__":
    animate.frame_svg=art.frame_svg
    result=preview_day1.preview(video=True)
    Path("out/provenance.json").write_text(json.dumps({"renderer":"original_graphic_novel_v1","old_scene_renderer_used":False,"publishing_authorized":False},indent=2))
    print(json.dumps(result))
