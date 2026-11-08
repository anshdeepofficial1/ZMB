"""First-frame approvals are never inferred from merely having a PNG."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import first_frame_review as fr
from visual_manifest import VisualContractError


class FirstFrameHumanReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.frame=self.root/"00.png"
        Image.new("RGB",(704,1248),(32,44,58)).save(self.frame)
        self.cast=self.root/"cast.json"
        self.props=self.root/"props.json"
        self.cast.write_text(json.dumps({"max":{"reference":"max.png","visual_identity":"adult Max"}}))
        self.props.write_text(json.dumps({"props":{}}))
        self.shot={
            "id":"s1_d001_00","image_path":str(self.frame),
            "prompt":"Max drives the one sedan in a carefully framed film shot.",
            "physical_direction":"Max drives a fixed sedan through a dark highway.",
            "characters":[{"id":"max"}], "prop_references":[],
        }
        self.editor={key:True for key in fr.CHECKS}

    def setup_patches(self):
        return (
            patch.object(fr,"CAST_BIBLE",self.cast),
            patch.object(fr,"PROP_BIBLE",self.props),
            patch.object(fr,"ROOT",self.root),
            patch("reference_review.verify_reference",
                  return_value={"file_sha256":"approved-max-face-sha"}),
        )

    def test_unreviewed_frame_cannot_be_animation_input(self):
        with self.setup_patches()[0],self.setup_patches()[1],self.setup_patches()[2],self.setup_patches()[3]:
            with self.assertRaisesRegex(VisualContractError,"human approval missing"):
                fr.verify_frame(self.shot)

    def test_signed_off_frame_is_bound_to_real_png_and_story(self):
        with self.setup_patches()[0],self.setup_patches()[1],self.setup_patches()[2],self.setup_patches()[3]:
            with self.assertRaisesRegex(VisualContractError,"ALL five"):
                fr.approve_frame(self.shot,reviewer="",confirmed={})
            receipt=fr.approve_frame(self.shot,reviewer="Film Editor",confirmed=self.editor)
            self.assertTrue(fr.verify_frame(self.shot))
            self.assertEqual(receipt["status"],"approved")
            alternate=dict(self.shot,physical_direction="Max teleports into another car.")
            with self.assertRaisesRegex(VisualContractError,"changed direction_sha256"):
                fr.verify_frame(alternate)
            Image.new("RGB",(704,1248),(92,18,29)).save(self.frame)
            with self.assertRaisesRegex(VisualContractError,"changed png_sha256"):
                fr.verify_frame(self.shot)

    def test_reference_sha_change_invalidates_scene(self):
        with self.setup_patches()[0],self.setup_patches()[1],self.setup_patches()[2],self.setup_patches()[3]:
            fr.approve_frame(self.shot,reviewer="Film Editor",confirmed=self.editor)
            with patch("reference_review.verify_reference",
                       return_value={"file_sha256":"new-face-sha"}):
                with self.assertRaisesRegex(VisualContractError,"changed canonical_references_sha256"):
                    fr.verify_frame(self.shot)


if __name__=="__main__":
    unittest.main()
