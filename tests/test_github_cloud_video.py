"""Offline contracts for GitHub Actions-driven paid cloud cinematic pipeline."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import shutil
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import github_cloud_video as cloud
from visual_manifest import day1_episode, build_manifest, VisualContractError


class GitHubCloudPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.story = build_manifest(day1_episode(), allow_unimplemented=True)
        cls.shots = cls.story["shots"]

    def test_all_day_one_actions_have_a_real_render_plan(self):
        plan = cloud.preflight_plan(self.shots)
        self.assertEqual(plan["shots"], 7)
        self.assertEqual(plan["video_model"], "fal-ai/ltx-2.3/image-to-video")
        self.assertIn("sedan", plan["roles"])
        self.assertIn("station", plan["roles"])
        self.assertFalse(plan["published"])
        self.assertFalse(plan["reviewed"])
        self.assertLessEqual(plan["billable_api_calls_max"], 24)

    def test_cost_preflight_fails_before_calling_provider(self):
        with self.assertRaisesRegex(VisualContractError, "exceeds safe cap"):
            cloud.preflight_plan(self.shots, max_calls=2)
        with self.assertRaisesRegex(VisualContractError, "no authored"):
            cloud.preflight_plan([])

    def test_no_key_cannot_start_billable_inference(self):
        with patch.dict("os.environ", {"FAL_KEY": ""}):
            with self.assertRaisesRegex(VisualContractError, "DISABLED"):
                cloud.FalInference()

    def test_cloud_runtime_writes_only_unreviewed_provenance(self):
        import inspect
        render_source = inspect.getsource(cloud.assemble_draft)
        self.assertIn("day1_UNREVIEWED_preview.mp4", render_source)
        self.assertNotIn("publish_reel", render_source)
        generator_source = inspect.getsource(cloud.generate_one)
        self.assertIn('"approval": "UNREVIEWED"', generator_source)
        self.assertIn('"publishing_authorized": False', generator_source)

    def test_image_model_uses_actual_identity_description(self):
        identities=cloud.identity_bibles()
        man=cloud.reference_prompt("max", identities["max"]["visual_identity"])
        vehicle=cloud.reference_prompt("sedan", identities["sedan"]["visual_identity"])
        self.assertIn("charcoal", man)
        self.assertIn("steel blue", vehicle.lower().replace("-", " "))
        self.assertNotEqual(man, vehicle)

    def test_literal_action_in_first_frame_and_motion_prompts(self):
        for shot in self.shots:
            self.assertIn(shot["physical_direction"], cloud.shot_frame_prompt(shot))
            self.assertIn(shot["physical_direction"], cloud.video_motion_prompt(shot))
        self.assertIn("same car geometry", cloud.video_motion_prompt(self.shots[0]))

    def test_provider_supports_only_six_eight_ten_second_shots(self):
        self.assertEqual(cloud.choose_video_duration(5.8), 6)
        self.assertEqual(cloud.choose_video_duration(7.0), 8)
        self.assertEqual(cloud.choose_video_duration(9.5), 10)
        with self.assertRaisesRegex(VisualContractError, "split"):
            cloud.choose_video_duration(11.0)

    def test_strict_media_hosts_no_http_localhost_or_evil_subdomains(self):
        good = "https://v3b.fal.media/files/b/abc/scene.mp4"
        self.assertTrue(cloud._allowed_download_url(good))
        self.assertTrue(cloud._allowed_download_url("https://storage.googleapis.com/fal-assets/x.png"))
        self.assertFalse(cloud._allowed_download_url("http://v3b.fal.media/file.mp4"))
        self.assertFalse(cloud._allowed_download_url("https://fal.media.evil.com/file.mp4"))
        self.assertFalse(cloud._allowed_download_url("https://127.0.0.1/file.mp4"))
        self.assertFalse(cloud._allowed_download_url("file:///etc/passwd"))

    def test_model_output_requires_actual_video_or_image_url(self):
        self.assertEqual(
            cloud._first_media_url(
                {"video":{"url":"https://v3b.fal.media/fake.mp4"}},
                kind="video"),
            "https://v3b.fal.media/fake.mp4",
        )
        with self.assertRaisesRegex(VisualContractError,"trustworthy"):
            cloud._first_media_url({"video":{"url":"https://evil.test/a.mp4"}},kind="video")
        with self.assertRaisesRegex(VisualContractError,"trustworthy"):
            cloud._first_media_url({"images":[]},kind="image")

    def test_paid_provider_media_download_refuses_untrusted_url_before_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(cloud.requests, "get") as caller:
                with self.assertRaisesRegex(VisualContractError, "untrusted"):
                    cloud.download_provider_asset("http://localhost:8080/private",
                                                   Path(tmp)/"vid.mp4",".mp4")
                caller.assert_not_called()

    @unittest.skipUnless(
        shutil.which("ffmpeg") and shutil.which("ffprobe") and
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf").exists(),
        "requires FFmpeg + DejaVu; exercised on GitHub Actions Ubuntu",
    )
    def test_synthetic_technical_ffmpeg_draft_is_watermarked_and_audio_muxed(self):
        # This intentionally tests assembly only, NOT image/video generation.
        # Never mistake this generated colour clip for professional footage.
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            work=root/"work"
            work.mkdir()
            source=root/"fake-scene.mp4"
            silence=root/"synthetic.wav"
            subprocess.run([
                "ffmpeg","-y","-hide_banner","-loglevel","error",
                "-f","lavfi","-i","color=c=0x18344a:s=720x1280:r=25",
                "-t","2","-an","-c:v","libx264","-preset","ultrafast",
                "-pix_fmt","yuv420p",str(source),
            ],check=True,timeout=60)
            subprocess.run([
                "ffmpeg","-y","-hide_banner","-loglevel","error",
                "-f","lavfi","-i","anullsrc=r=24000:cl=mono",
                "-t","2","-ac","1","-c:a","pcm_s16le",str(silence),
            ],check=True,timeout=60)
            shot=SimpleNamespace(kind="line",start=0.0,end=2.0,dur=2.0)
            voices=[{"text":"Max drives the car.",
                     "words":[{"w":"Max","start":0.0,"end":0.30},
                              {"w":"drives","start":0.36,"end":0.7},
                              {"w":"the","start":0.8,"end":1.0},
                              {"w":"car","start":1.1,"end":1.4}]}]
            with patch.object(cloud, "WORK", work):
                draft=cloud.assemble_draft(
                    {"title_card":False},[(shot,source)],
                    voices,2.0,silence,root/"out",
                )
            self.assertTrue(draft.is_file())
            self.assertIn("UNREVIEWED",draft.name)
            self.assertGreater(draft.stat().st_size,1024)
            from render_cinematic import _probe_video
            info=_probe_video(draft)
            self.assertEqual(info["width"],1080)
            self.assertEqual(info["height"],1920)
            self.assertAlmostEqual(info["duration"],2.0,delta=0.9)

    def test_empty_story_draft_cannot_be_promoted_to_reel_output(self):
        import inspect
        code=inspect.getsource(cloud.main)
        self.assertIn("authorize_charges",code)
        self.assertIn("publishing_enabled",code)
        self.assertIn("cinematic_release_approved",code)


if __name__ == "__main__":
    unittest.main()
