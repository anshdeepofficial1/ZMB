import json
import sys
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from visual_manifest import day1_episode, build_manifest, VisualContractError
from render_cinematic import required_clips, validate_assets, build_subtitles


class DayOneVisualContractTests(unittest.TestCase):
    def test_day1_has_seven_distinct_visible_physical_beats(self):
        ep = day1_episode()
        spec = build_manifest(ep)
        beats = [s["beat"] for s in spec["shots"]]
        self.assertEqual(beats, [
            "car_driving", "engine_stall", "car_interior",
            "flashlight_exit", "spot_station", "door_shadow", "door_handle",
        ])
        self.assertIn("headlights", spec["shots"][1]["narration"].lower())
        self.assertIn("flashlight", spec["shots"][3]["narration"].lower())
        self.assertIn("door handle", spec["shots"][-1]["narration"].lower())
        self.assertEqual(len({s["id"] for s in spec["shots"]}), 7)
        self.assertFalse(spec["approval"]["approved"])

    def test_reject_missing_beat_rather_than_generic_walk_cycle(self):
        ep = day1_episode()
        ep["lines"][0]["shot"].pop("beat")
        with self.assertRaisesRegex(VisualContractError, "no physical action"):
            build_manifest(ep)

    def test_reject_driving_audio_with_wrong_visual(self):
        ep = day1_episode()
        ep["lines"][0]["shot"]["beat"] = "door_shadow"
        with self.assertRaisesRegex(VisualContractError, "not visibly represented"):
            build_manifest(ep)

    def test_all_137_narrated_lines_have_physical_directions(self):
        from visual_manifest import DIRECTIONS, STORY
        directions = json.loads(DIRECTIONS.read_text(encoding="utf-8"))["arcs"]
        story = json.loads(STORY.read_text(encoding="utf-8"))["arcs"]
        total = 0
        for arc_id, arc in story.items():
            for node_id, node in arc["nodes"].items():
                expected = len(node.get("lines") or [])
                actual = directions[arc_id][node_id]
                self.assertEqual(len(actual), expected, (arc_id, node_id))
                for line in actual:
                    self.assertGreaterEqual(len(line["action"]), 15)
                    self.assertTrue(line["props"])
                    self.assertFalse(line["reviewed"])
                total += expected
        self.assertEqual(total, 137)

    def test_cinematic_future_scene_prompts_are_distinct_and_grounded(self):
        from visual_manifest import STORY
        story = json.loads(STORY.read_text(encoding="utf-8"))
        ep = day1_episode()
        ep["node"] = "store_sound"
        ep["lines"] = story["arcs"]["road"]["nodes"]["store_sound"]["lines"]
        spec = build_manifest(ep, allow_unimplemented=True)
        self.assertEqual(len(spec["shots"]), 5)
        self.assertEqual(spec["shots"][2]["beat"], "cinematic_asset_only")
        self.assertIn("staff only door", spec["shots"][2]["physical_direction"].lower())
        self.assertIn("door", " ".join(spec["shots"][2]["required_props"]).lower())

    def test_publish_guard_blocks_unsafe_production(self):
        import os
        import subprocess
        env = dict(os.environ)
        env["ZMB_PUBLISH_ENABLED"] = "0"
        process = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "run_cycle.py"), "--force-publish"],
            capture_output=True, text=True, env=env, check=False
        )
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("PUBLISHING PAUSED", process.stderr + process.stdout)

    def test_reject_unmapped_future_story(self):
        from visual_manifest import STORY
        doc = json.loads(STORY.read_text(encoding="utf-8"))
        ep = day1_episode()
        ep["node"] = "store_sound"
        ep["lines"] = doc["arcs"]["road"]["nodes"]["store_sound"]["lines"]
        with self.assertRaisesRegex(VisualContractError, "no physical action"):
            build_manifest(ep)

    def test_reject_missing_generated_footage(self):
        ep = day1_episode()
        shots = [SimpleNamespace(kind="line", dur=1.25)]
        required = required_clips(ep, shots)
        self.assertTrue(str(required[0][1]).endswith("road/intro/00.mp4"))
        with self.assertRaisesRegex(VisualContractError, "Missing scene-specific"):
            validate_assets(ep, shots)

    def test_ass_captions_follow_shot_start_time(self):
        shots = [SimpleNamespace(kind="line", start=2.5, dur=3, end=5.5)]
        voices = [{"text": "This is a test.", "words": [
            {"w": "This", "start": 0.2, "end": 0.5},
            {"w": "is", "start": 0.6, "end": 0.8},
            {"w": "a", "start": 0.9, "end": 1.0},
            {"w": "test.", "start": 1.1, "end": 1.5},
        ]}]
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "subtitle.ass"
            build_subtitles(shots, voices, dest)
            rendered = dest.read_text(encoding="utf-8")
            self.assertIn("0:00:02.70", rendered)
            self.assertIn("This is a test.", rendered)


if __name__ == "__main__":
    unittest.main()
