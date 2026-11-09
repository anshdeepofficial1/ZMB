"""Art-direction regression: ZMB must be *animated* (not realistic footage).

Passing these tests confirms prompt/style contracts ONLY, not rendered quality.
"""
import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))

from art_direction import STYLE_ID, style_header, scene_prompt, animation_prompt
from free_first_frame import frame_prompt
from free_video_preview import prompt_for_real_motion
from visual_manifest import build_manifest, day1_episode


class AnimatedStoryStyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=build_manifest(day1_episode(), allow_unimplemented=True)
        cls.shots=cls.manifest["shots"]

    def test_every_narrated_scene_uses_consistent_premium_3d(self):
        self.assertEqual(len(self.shots),7)
        self.assertTrue(STYLE_ID.startswith("zmb_premium_animated_3d_"))
        for shot in self.shots:
            still=frame_prompt(shot).lower()
            moving=prompt_for_real_motion(shot).lower()
            storyboard=shot["prompt"].lower()
            self.assertIn("3d animated",still)
            self.assertIn("3d animated",moving)
            self.assertIn("3d animated",storyboard)
            self.assertIn(shot["physical_direction"].lower(),still)
            self.assertIn(shot["physical_direction"].lower(),moving)
            self.assertIn(shot["physical_direction"].lower(),storyboard)
            self.assertIn("not live action",moving)
            self.assertIn("not a real photographic person",still)
            self.assertIn("flat 2d shapes",still)
            self.assertIn("flat 2d shapes",moving)

    def test_max_stays_inside_vehicle_biscuit_identity_and_light_palette(self):
        intro=self.shots[0]
        still=scene_prompt(intro).lower()
        motion=animation_prompt(intro).lower()
        for word in ("fully seated","inside","seatbelt","steering wheel",
                     "navy","amber","no dog","steel-blue","no dawn"):
            self.assertIn(word,still)
        for phrase in ("stays buckled","road lines moving", "headlights",
                       "original animated character","3d animated"):
            self.assertIn(phrase,motion)
        self.assertIn("no giant empty sky",style_header().lower())

    def test_live_action_old_video_sidecar_without_style_is_rejected(self):
        import inspect
        import free_video_preview
        source=inspect.getsource(free_video_preview.verify_source)
        self.assertIn("data.get(\"art_style\") != STYLE_ID",source)
        self.assertIn("Cannot animate old photorealistic source image",source)

    def test_art_direction_is_presentation_not_quality_approval(self):
        import inspect
        import free_first_frame
        source=inspect.getsource(free_first_frame.generate)
        self.assertIn('"character_identity_status": "UNREVIEWED"',source)
        self.assertIn('"instagram_publishing_authorized": False',source)


if __name__=="__main__":
    unittest.main()
