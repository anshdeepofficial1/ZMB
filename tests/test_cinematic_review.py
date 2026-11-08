"""Exact-file human approval checks: updated media or story must invalidate review."""
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from cinematic_review import approve, verify, verify_manifest, CHECKS, receipt_path
from visual_manifest import VisualContractError


class CinematicReviewTests(unittest.TestCase):
    def test_real_manual_review_receipt_is_hash_bound(self):
        with tempfile.TemporaryDirectory() as folder:
            clip = Path(folder) / "00.mp4"
            clip.write_bytes(b"a validly-sized fixture, NOT production media" * 100)
            shot = {"id": "s1_d001_00", "prompt": "Actual driving", "video_path": str(clip)}
            with self.assertRaisesRegex(VisualContractError, "explicitly confirm"):
                approve(shot, reviewer="Editor", checks=list(CHECKS[:-1]))
            receipt = approve(shot, reviewer="Editor", checks=list(CHECKS))
            self.assertTrue(receipt_path(clip).exists())
            self.assertEqual(receipt["status"], "approved")
            self.assertEqual(verify(shot)["video_sha256"], receipt["video_sha256"])
            self.assertTrue(verify_manifest({"shots": [shot]})["approved"])

    def test_replace_media_invalidates_approval(self):
        with tempfile.TemporaryDirectory() as folder:
            clip = Path(folder) / "00.mp4"
            clip.write_bytes(b"A" * 2048)
            shot = {"id": "s1_d001_00", "prompt": "Visible car engine stall", "video_path": str(clip)}
            approve(shot, reviewer="Editor", checks=list(CHECKS))
            clip.write_bytes(b"B" * 2048)
            with self.assertRaisesRegex(VisualContractError, "changed after human approval"):
                verify(shot)

    def test_story_edit_invalidates_approval(self):
        with tempfile.TemporaryDirectory() as folder:
            clip = Path(folder) / "00.mp4"
            clip.write_bytes(b"A" * 2048)
            shot = {"id": "s1_d001_00", "prompt": "Vehicle stops on road", "video_path": str(clip)}
            approve(shot, reviewer="Editor", checks=list(CHECKS))
            shot["prompt"] = "Vehicle crashes into a building"
            with self.assertRaisesRegex(VisualContractError, "narration/story direction changed"):
                verify(shot)

    def test_review_cannot_claim_missing_asset(self):
        with tempfile.TemporaryDirectory() as folder:
            shot = {"id": "s1_d001_00", "prompt": "Scene", "video_path": str(Path(folder) / "no.mp4")}
            with self.assertRaisesRegex(VisualContractError, "missing/empty"):
                approve(shot, reviewer="Editor", checks=list(CHECKS))

    def test_review_requires_named_person(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.mp4"
            path.write_bytes(b"A" * 2048)
            shot = {"id": "s1_d001_00", "prompt": "Scene", "video_path": str(path)}
            with self.assertRaisesRegex(VisualContractError, "named human reviewer"):
                approve(shot, reviewer="   ", checks=list(CHECKS))


if __name__ == "__main__":
    unittest.main()
