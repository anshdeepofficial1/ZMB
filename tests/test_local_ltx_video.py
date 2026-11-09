"""Real video-model planning, GPU safety and Instagram-safe caption tests.

All tests are CPU-only. Passing them does not imply model weights were run.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ltx_local_video as local
from render_cinematic import build_subtitles
from visual_manifest import VisualContractError, build_manifest, day1_episode


class LocalModelPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shots = build_manifest(day1_episode(), allow_unimplemented=True)["shots"]

    def test_exact_day_one_actions_preserved_not_stock_footage(self):
        self.assertEqual(len(self.shots), 7)
        for shot in self.shots:
            prompt = local.scene_prompt(shot).lower()
            self.assertIn(shot["physical_direction"].lower(), prompt)
            self.assertIn("3d animated", prompt)
            self.assertIn("motion", prompt)
            self.assertNotIn("flat cartoon", prompt)
        self.assertIn("wheel", local.scene_prompt(self.shots[0]).lower())

    def test_model_command_is_actual_open_source_image_to_video(self):
        profile = local.PROFILES["quality"]
        cmd = local.build_command(
            ROOT / ".models" / "LTX-Video", self.shots[0], profile,
            ROOT / "work" / "ltx-plan",
        )
        self.assertEqual(cmd[0], sys.executable)
        self.assertIn("inference.py", cmd[1])
        self.assertEqual(cmd[cmd.index("--conditioning_start_frames") + 1], "0")
        self.assertTrue(cmd[cmd.index("--conditioning_media_paths") + 1].endswith("00.png"))
        self.assertTrue(cmd[cmd.index("--pipeline_config") + 1].endswith(profile.yaml))
        self.assertEqual(cmd[cmd.index("--height") + 1], "1248")
        self.assertEqual(cmd[cmd.index("--offload_to_cpu") + 1], "true")
        frames=int(cmd[cmd.index("--num_frames") + 1])
        self.assertEqual((frames-1)%8,0)
        self.assertTrue(9<=frames<=241)
        self.assertNotIn("http", " ".join(cmd))

    def test_studio_quality_is_not_confused_with_diagnostic_profile(self):
        self.assertEqual(local.PROFILES["test"].min_vram_gb, 8)
        self.assertEqual(local.PROFILES["studio"].min_vram_gb, 24)
        self.assertIn("13b", local.PROFILES["studio"].yaml)
        self.assertNotIn("13b", local.PROFILES["quality"].yaml)

    def test_four_gig_gpu_is_blocked_from_professional_profile(self):
        with patch.object(local,"detect_gpu",return_value=("RTX 3050 4GB",4)):
            with self.assertRaisesRegex(VisualContractError, "4GB VRAM"):
                local.validate_gpu(local.PROFILES["quality"])
            with self.assertRaisesRegex(VisualContractError, "profile test"):
                local.validate_gpu(local.PROFILES["studio"],experimental_low_vram=True)
            self.assertEqual(
                local.validate_gpu(local.PROFILES["test"],experimental_low_vram=True),
                "RTX 3050 4GB"
            )

    def test_missing_gpu_is_hard_failure_not_cpu_model_fake(self):
        with patch.object(local, "detect_gpu", side_effect=VisualContractError("No CUDA video-generation GPU")):
            with self.assertRaisesRegex(VisualContractError, "No CUDA"):
                local.validate_gpu(local.PROFILES["quality"])

    def test_scene_png_is_required_and_not_a_procedural_fallback(self):
        shot = dict(self.shots[0])
        with tempfile.TemporaryDirectory() as tmp:
            shot["image_path"] = str(Path(tmp) / "no_scene.png")
            with self.assertRaisesRegex(VisualContractError, "Missing scene-specific FIRST FRAME"):
                local.verify_source_frame(shot)

    def test_ltx_dry_run_is_available_without_cuda_or_weights(self):
        run = subprocess.run(
            [sys.executable, str(ROOT/"scripts"/"ltx_local_video.py"),
             "--day1", "--shot", "0", "--dry-run"],
            capture_output=True,text=True,check=False,
        )
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertIn("PLAN ONLY",run.stdout)
        self.assertIn("car_driving",run.stdout)
        self.assertNotIn("publishing_authorized\": true",run.stdout)


class CinematicCaptionSafetyTests(unittest.TestCase):
    def test_caption_layout_does_not_use_old_bottom_screen_hud(self):
        shots=[SimpleNamespace(kind="line",start=0.0,dur=5.0,end=5.0)]
        voices=[{
            "text": "Max drives alone. His headlights start flickering.",
            "words": [
                {"w":w.strip(".").strip(), "start":i*0.45,
                 "end":i*0.45+0.39}
                for i,w in enumerate(
                    "Max drives alone His headlights start flickering".split()
                )
            ],
        }]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"captions.ass"
            build_subtitles(shots,voices,path)
            content=path.read_text(encoding="utf-8")
            self.assertIn("DejaVu Sans,61",content)
            self.assertIn(",96,230,410,1",content)
            self.assertNotIn("Barlow,65",content)
            self.assertIn("Max drives alone.",content)
            self.assertIn("His headlights start",content)
            self.assertIn("flickering.",content)
            self.assertNotIn("HUD",content)


if __name__ == "__main__":
    unittest.main()
