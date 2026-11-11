"""Contract tests: original 2D vector animation, no model or paid API."""
import inspect
import json
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import animate
import render
from visual_manifest import build_manifest, day1_episode


class Pure2DTests(unittest.TestCase):
    def test_config_is_procedural_and_not_ai(self):
        cfg = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["visual_mode"], "procedural")
        self.assertFalse(cfg["ai_story_generation"])
        self.assertFalse(cfg["procedural_release_approved"])
        self.assertEqual(cfg["narration_engine"], "espeak-ng")

    def test_seven_unique_physically_moving_story_beats(self):
        manifest = build_manifest(day1_episode())
        self.assertEqual(len(manifest["shots"]), 7)
        for shot in manifest["shots"]:
            self.assertTrue(shot["physical_direction"])
            before = animate.narrative_beat_layer({"beat": shot["beat"]}, .18)
            after = animate.narrative_beat_layer({"beat": shot["beat"]}, 1.35)
            self.assertTrue(before, shot["beat"])
            self.assertNotEqual(before, after, f"{shot['beat']} did not animate")

    def test_no_gas_station_before_reveal(self):
        inside = animate.narrative_beat_layer({"beat": "car_interior"}, 1.3)
        self.assertNotIn("OPEN 24 HOURS", inside)
        self.assertIn("STALLED", inside)

    def test_renderer_does_not_call_ai_modules(self):
        source = inspect.getsource(render.render_episode)
        self.assertNotIn("render_ai_video(", source)
        self.assertNotIn("render_storyboard(", source)
        self.assertIn("procedural_2d_no_ai", source)

    def test_caption_visual_safe_zone_is_fixed(self):
        from animate import caption_layer, Texts
        from svgrender import font_map
        Text = Texts(font_map(ROOT))
        chunks = [{
            "start": 0.0, "end": 3.2,
            "words": [
                {"w": "Max", "start": 0.0, "end": .5},
                {"w": "drives", "start": .6, "end": 1.0},
                {"w": "alone.", "start": 1.1, "end": 2.2},
            ]
        }]
        frame_a = caption_layer(chunks, .8, Text)
        frame_b = caption_layer(chunks, 1.4, Text)
        self.assertIn('y="1125"',frame_a)
        self.assertIn('y="1125"',frame_b)
        self.assertIn('y="1195"',frame_a)
        self.assertIn('y="1195"',frame_b)
        self.assertNotIn('y="932" width="840"',frame_a)

    def test_no_early_highway_gas_station_and_present_hook(self):
        from animate import opening_hook_layer, Shot
        import scenes
        defs, layers = scenes.highway("night", "tense", 12)
        self.assertNotIn("OPEN 24 HOURS", "".join(x[1] for x in layers))
        hook = opening_hook_layer(Shot("line", 0, 5, meta={"beat": "car_driving"}), .6)
        self.assertIn("THE LAST DRIVE", hook)
        self.assertIn("2:47 AM", hook)

    def test_original_audio_synth_is_non_ai_and_has_real_wav(self):
        import sound_design
        from types import SimpleNamespace
        import wave
        sequence=[
            SimpleNamespace(kind="line",meta={"beat":"car_driving"},start=0,end=2),
            SimpleNamespace(kind="line",meta={"beat":"engine_stall"},start=2,end=4),
            SimpleNamespace(kind="line",meta={"beat":"flashlight_exit"},start=4,end=6),
            SimpleNamespace(kind="line",meta={"beat":"spot_station"},start=6,end=8),
            SimpleNamespace(kind="line",meta={"beat":"door_handle"},start=8,end=10),
        ]
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"sound.wav"
            info=sound_design.synthesize(sequence,10.0,path)
            self.assertFalse(info["ai_generated"])
            with wave.open(str(path),"rb") as wav:
                self.assertEqual(wav.getframerate(),24000)
                self.assertEqual(wav.getnframes(),240000)
            self.assertGreater(path.stat().st_size,400000)

    def test_caption_config_keeps_all_words_visible(self):
        cfg = json.loads((ROOT / "config.example.json").read_text())
        self.assertLessEqual(cfg["render"]["caption_max_words"],4)
        self.assertLessEqual(cfg["render"]["caption_max_width"],755)


    def test_backpack_follows_actor_and_stays_on_max_after_exit(self):
        import characters
        moving=characters.render_actor("max","walk",0.6,size=600,backpack=True)
        turning=characters.render_actor("max","look",1.8,size=600,backpack=True)
        unladen=characters.render_actor("max","walk",.6,size=600,backpack=False)
        self.assertIn("#965533",moving)
        self.assertIn("#965533",turning)
        self.assertNotIn("#965533",unladen)
        self.assertNotEqual(moving,turning)

    def test_driver_head_uses_same_original_2d_face_design(self):
        driving=animate.narrative_beat_layer({"beat":"car_driving"},.6)
        self.assertIn("#fff9f0",driving)
        self.assertIn("#f5bd96",driving)

    def test_flashlight_is_attached_to_original_2d_max_hand(self):
        import characters
        actor = characters.render_actor("max","walk_flashlight",1.5,size=600)
        self.assertIn("#fff3a4",actor)
        self.assertIn("translate(",actor)
        self.assertIn("#fff8c1",actor)
        plain = characters.render_actor("max","walk",1.5,size=600)
        self.assertNotIn("#fff3a4",plain)


    def test_offline_espeak_only_and_real_voice_no_silent_fallback(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            def mocked_run(cmd, **kwargs):
                calls.append(cmd)
                if cmd[0] == "espeak-ng":
                    Path(cmd[cmd.index("-w")+1]).write_bytes(b"audio bytes" * 200)
            with patch.object(render, "run", side_effect=mocked_run), \
                 patch.object(render, "_probe_dur", return_value=2.5):
                out = render.synthesize_voices(
                    {"render": {"gap_seconds": 0.4}},
                    {"lines": [{"text": "Max drives a car.", "shot": {}}]},
                    Path(directory), Log=lambda *_: None
                )
            self.assertEqual(len(out), 1)
            self.assertEqual(calls[0][0], "espeak-ng")
            self.assertEqual(calls[1][0], "ffmpeg")
            self.assertEqual(out[0]["timings"], "estimated")


if __name__ == "__main__":
    unittest.main()
