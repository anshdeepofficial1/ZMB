"""Offline contract tests for single zero-rupee model video generation."""
import sys
import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import free_video_preview as clip
from visual_manifest import build_manifest,day1_episode,VisualContractError


class FreeVideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shot=build_manifest(day1_episode(),allow_unimplemented=True)["shots"][0]

    def test_clip_model_is_official_free_demo_with_physical_action(self):
        self.assertEqual(clip.SPACE,"Lightricks/LTX-2.5")
        prompt=clip.prompt_for_real_motion(self.shot)
        self.assertIn(self.shot["physical_direction"],prompt)
        for required in ("drives forward","hands make believable", "headlights visibly pulse","morphing"):
            self.assertIn(required.lower(),prompt.lower())

    def test_real_first_frame_provenance_cannot_be_swapped(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"shot_00.png"
            Image.new("RGB",(768,1376),(90,110,135)).save(file)
            data={
                "shot_id":self.shot["id"],
                "model_space":"black-forest-labs/FLUX.1-schnell",
                "art_style":"zmb_premium_animated_3d_v1",
                "file_sha256":hashlib.sha256(file.read_bytes()).hexdigest(),
            }
            file.with_suffix(".json").write_text(json.dumps(data))
            self.assertEqual(clip.verify_source(self.shot,file)["image_width"],768)
            Image.new("RGB",(768,1376),(18,42,33)).save(file)
            with self.assertRaisesRegex(VisualContractError,"changed"):
                clip.verify_source(self.shot,file)

    def test_live_action_reference_is_rejected_even_when_png_sha_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"shot_00.png"
            Image.new("RGB",(768,1376),(40,68,95)).save(file)
            file.with_suffix(".json").write_text(json.dumps({
                "shot_id":self.shot["id"],
                "model_space":"black-forest-labs/FLUX.1-schnell",
                "file_sha256":hashlib.sha256(file.read_bytes()).hexdigest()
            }))
            with self.assertRaisesRegex(VisualContractError,"old photorealistic"):
                clip.verify_source(self.shot,file)

    def test_frame_requires_provenance_not_generic_portrait(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"shot_00.png"
            Image.new("RGB",(768,1376)).save(file)
            with self.assertRaisesRegex(VisualContractError,"provenance"):
                clip.verify_source(self.shot,file)

    def test_only_one_call_and_requires_manual_free_quota_opt_in(self):
        import inspect
        source=inspect.getsource(clip.main)
        self.assertIn("accept_free_quota",source)
        self.assertNotIn("FAL_KEY",inspect.getsource(clip))
        self.assertIn("UNREVIEWED",inspect.getsource(clip.generate_one))
        self.assertNotIn("instagram",inspect.getsource(clip.generate_one).lower())

    def test_no_nonportrait_or_tiny_motion_can_be_accepted(self):
        import inspect
        text=inspect.getsource(clip.ffprobe)
        self.assertTrue('9/16' in text or '9 / 16' in text)
        self.assertIn('3.0 <= duration <= 6.0',text)


if __name__=="__main__":
    unittest.main()
