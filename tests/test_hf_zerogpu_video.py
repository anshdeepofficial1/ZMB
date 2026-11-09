"""Zero-rupee regression tests: no billable inference, no fake premium claim."""
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"scripts"))
import hf_zerogpu_video as z
from visual_manifest import VisualContractError, build_manifest, day1_episode


class ZeroBudgetTests(unittest.TestCase):
    def test_plan_is_strictly_free(self):
        p=z.planned()
        self.assertEqual(p["budget_rupees"],0)
        self.assertEqual(p["monthly_paid_api_calls"],0)
        self.assertEqual(p["clips_per_invocation_max"],1)
        self.assertFalse(p["paid_fallback_allowed"])
        self.assertFalse(p["guaranteed_daily_full_episode"])
        self.assertFalse(p["instagram_publishing"])

    def test_public_probe_does_not_send_inference_request(self):
        result=Mock()
        result.json.return_value={
            "private": False,
            "runtime": {"stage":"RUNNING","hardware":"zero-a10g"},
        }
        with patch.object(z.requests, "get", return_value=result) as request:
            status=z.space_info()
            self.assertTrue(status["free_zero_gpu_verified"])
            self.assertTrue(status["no_inference_requested"])
            self.assertEqual(status["billable_calls"],0)
            request.assert_called_once()
            self.assertEqual(request.call_args.args[0],z.SPACE_API)

    def test_non_free_hardware_not_confirmed(self):
        result=Mock()
        result.json.return_value={
            "private":False,"runtime":{"stage":"RUNNING","hardware":"a100-large"},
        }
        with patch.object(z.requests,"get",return_value=result):
            self.assertFalse(z.space_info()["free_zero_gpu_verified"])

    def test_missing_approved_cinematic_frame_prevents_gpu_use(self):
        shot=build_manifest(day1_episode(),allow_unimplemented=True)["shots"][0]
        with patch.object(z, "approved_scene", side_effect=VisualContractError("review missing")):
            with self.assertRaisesRegex(VisualContractError,"review missing"):
                z.generate_one_clip(shot,token="hf_test_fake",output=Path("/tmp/fake"))

    def test_missing_free_token_does_not_consume_quota(self):
        shot=build_manifest(day1_episode(),allow_unimplemented=True)["shots"][0]
        with patch.object(z,"approved_scene") as image:
            with self.assertRaisesRegex(VisualContractError,"Missing free"):
                z.generate_one_clip(shot,token="",output=Path("/tmp/fake"))
            image.assert_not_called()

    def test_enforces_daily_shared_gpu_time_and_paid_account_rejection(self):
        from huggingface_hub import HfApi
        with patch.object(HfApi, "get_zero_gpu_quota", return_value=SimpleNamespace(
            base=300,remaining=95
        )):
            with self.assertRaisesRegex(VisualContractError,"remaining 95"):
                z._free_account_quota("hf_test_fake")
        with patch.object(HfApi,"get_zero_gpu_quota",return_value=SimpleNamespace(
            base=2400,remaining=2400
        )):
            with self.assertRaisesRegex(VisualContractError,"paid/extended"):
                z._free_account_quota("hf_test_fake")

    def test_no_unauthorized_paid_fallback_code(self):
        import inspect
        s=inspect.getsource(z)
        for forbidden in ("fal_client","FAL_KEY","I_ACCEPT_PROVIDER_CHARGES",
                          "replicate.Client","billing_enabled"):
            self.assertNotIn(forbidden,s)


if __name__=="__main__":
    unittest.main()
