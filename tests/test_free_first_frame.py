"""Offline tests for zero-cost Hugging Face FLUX cinematic first frames."""
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import free_first_frame as first
from visual_manifest import build_manifest,day1_episode,VisualContractError


class FreeFirstFrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shots=build_manifest(day1_episode(),allow_unimplemented=True)["shots"]

    def test_shot_zero_has_real_visual_action_not_generic_cartoon(self):
        shot=self.shots[0]
        prompt=first.frame_prompt(shot)
        self.assertIn(shot["physical_direction"],prompt)
        self.assertIn("steel-blue",prompt)
        self.assertIn("Max",prompt)
        self.assertIn("No title",prompt)
        self.assertIn("live-action",prompt.lower())
        self.assertIn("center",prompt.lower())

    def test_source_model_is_free_shared_gpu(self):
        self.assertEqual(first.MODEL,"black-forest-labs/FLUX.1-schnell")
        self.assertEqual(first.WIDTH%32,0)
        self.assertEqual(first.HEIGHT%32,0)
        self.assertAlmostEqual(first.WIDTH/first.HEIGHT,9/16,delta=0.045)

    def test_quota_requires_verified_free_account(self):
        from huggingface_hub import HfApi
        with patch.object(HfApi,"whoami",return_value={"isPro":False}):
            with patch.object(HfApi,"get_zero_gpu_quota",
                              return_value=SimpleNamespace(base=300,remaining=250)):
                self.assertEqual(first.verify_quota("hf_fake")["remaining_before"],250)
            with patch.object(HfApi,"get_zero_gpu_quota",
                              return_value=SimpleNamespace(base=300,remaining=5)):
                with self.assertRaisesRegex(VisualContractError,"Only"):
                    first.verify_quota("hf_fake")
            with patch.object(HfApi,"get_zero_gpu_quota",
                              return_value=SimpleNamespace(base=2400,remaining=2400)):
                with self.assertRaisesRegex(VisualContractError,"300-second"):
                    first.verify_quota("hf_fake")
        with patch.object(HfApi,"whoami",return_value={"isPro":True}):
            with self.assertRaisesRegex(VisualContractError,"requires verified Free"):
                first.verify_quota("hf_fake")

    def test_read_only_token_quota_403_falls_back_safely_for_free_account(self):
        from huggingface_hub import HfApi
        with patch.object(HfApi,"whoami",return_value={"isPro":False}), patch.object(
            HfApi,"get_zero_gpu_quota",side_effect=PermissionError("403 Forbidden")
        ):
            proof=first.verify_quota("hf_free_readonly")
        self.assertIsNone(proof["remaining_before"])
        self.assertEqual(proof["base"],300)
        self.assertIn("provider-enforced",proof["quota_protection"])

    def test_missing_token_blocks_inference(self):
        with self.assertRaisesRegex(VisualContractError,"HF_TOKEN"):
            first.verify_quota("")

    def test_invalid_model_response_is_not_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"fake.png"
            self.assertFalse(file.exists())
            with self.assertRaisesRegex(VisualContractError,"downloadable image"):
                first._result_file({"not_an_image":1})
            with self.assertRaisesRegex(VisualContractError,"missing or empty"):
                first._result_file(str(file))
            self.assertFalse(file.exists())

    def test_generation_requires_user_free_quota_authorization(self):
        import inspect
        source=inspect.getsource(first.main)
        self.assertIn("accept_free_quota",source)
        self.assertNotIn("FalInference",source)
        self.assertIn("UNREVIEWED FIRST FRAME",source)


if __name__=="__main__":
    unittest.main()
