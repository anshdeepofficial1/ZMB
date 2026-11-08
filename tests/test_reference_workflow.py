"""Verification of original references without inventing actual production assets."""
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import reference_review as rr
from reference_candidates import reference_prompt, subjects
from visual_manifest import VisualContractError


class ReferenceApprovalTests(TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.identity={
            "reference":"assets/character_refs/max.png",
            "visual_identity":"One exact Max with charcoal jacket, brown pants and dark hair",
        }
        self.candidate=self.root/"out"/"reference_candidates"/"max"/"candidate_01.png"
        self.candidate.parent.mkdir(parents=True)
        Image.new("RGB",(768,1280),(53,64,84)).save(self.candidate)

    def test_reference_must_be_actually_reviewed(self):
        with patch.object(rr,"ROOT",self.root):
            with self.assertRaisesRegex(VisualContractError,"real visual inspection"):
                rr.approve_candidate("max",self.candidate,self.identity,reviewer="",manually_inspected=False)
            self.assertFalse((self.root/self.identity["reference"]).exists())

    def test_approved_png_is_hash_and_identity_bound(self):
        with patch.object(rr,"ROOT",self.root):
            record=rr.approve_candidate("max",self.candidate,self.identity,
                 reviewer="Human Editor",manually_inspected=True)
            self.assertEqual(record["status"],"approved")
            self.assertEqual(record["role"],"max")
            self.assertTrue(rr.verify_reference("max",self.identity,root=self.root))
            with self.assertRaisesRegex(VisualContractError,"refuse overwrite"):
                rr.approve_candidate("max",self.candidate,self.identity,
                    reviewer="Human Editor",manually_inspected=True)
            Image.new("RGB",(768,1280),(31,29,30)).save(self.root/self.identity["reference"])
            with self.assertRaisesRegex(VisualContractError,"changed since approval"):
                rr.verify_reference("max",self.identity,root=self.root)

    def test_changing_identity_bible_invalidates_previous_approval(self):
        with patch.object(rr,"ROOT",self.root):
            rr.approve_candidate("max",self.candidate,self.identity,
                reviewer="Human Editor",manually_inspected=True)
            new_identity=dict(self.identity,visual_identity="Different face, red coat")
            with self.assertRaisesRegex(VisualContractError,"identity bible changed"):
                rr.verify_reference("max",new_identity,root=self.root)

    def test_wrong_role_reference_cannot_be_approved(self):
        with patch.object(rr,"ROOT",self.root):
            with self.assertRaisesRegex(VisualContractError,"candidate for this exact role"):
                rr.approve_candidate("ada",self.candidate,self.identity,
                    reviewer="Human Editor",manually_inspected=True)

    def test_generator_prompts_contain_specific_original_identity(self):
        cast=subjects()
        max_prompt=reference_prompt("max",cast["max"],1)
        biscuit_prompt=reference_prompt("biscuit",cast["biscuit"],1)
        sedan_prompt=reference_prompt("sedan",cast["sedan"],1)
        self.assertIn("charcoal",max_prompt.lower())
        self.assertIn("tan",biscuit_prompt.lower())
        self.assertIn("sedan",sedan_prompt.lower())
        self.assertNotEqual(max_prompt,biscuit_prompt)


if __name__=="__main__":
    main()
