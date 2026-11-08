"""Story-to-video integrity tests for non-first episodes and real voting."""
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"scripts"))

import engine
from visual_manifest import build_manifest


class StoryAndBranchContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.story=engine.load_scenarios()
        cls.cfg=json.loads((ROOT/"config.example.json").read_text(encoding="utf-8"))

    def state(self, node="intro", last=None):
        return {
            "arc":"road","season":1,"day":1,
            "node":node, "stats":{"hp":100,"noise":20,"food":60,"dog":70},
            "history":[],"recent_hashtags":[], "last_episode":last
        }

    def test_no_vote_is_never_misrepresented_as_audience_choice(self):
        res={"node_id":"store_sound","kind":"vote","total":0,"pct":0,
             "fallback":True,"winner_text":"RUN - get outside"}
        self.assertIsNone(engine.recap_line(res))

    def test_actual_vote_results_are_caption_only_not_unillustrated_audio(self):
        ep=engine.build_episode(self.state("store_sound"),self.story,self.cfg,
             recap="Previously, viewers chose RUN (67%).")
        self.assertEqual(len(ep["lines"]),len(self.story["arcs"]["road"]["nodes"]["store_sound"]["lines"]))
        self.assertNotIn("Previously",ep["narration"][0])
        self.assertIn("Previously, viewers chose RUN",ep["caption"])
        self.assertEqual(len(build_manifest(ep,allow_unimplemented=True)["shots"]),len(ep["lines"]))

    def test_first_thing_spoken_is_actual_scene_hook_not_votes(self):
        ep=engine.build_episode(self.state("intro"),self.story,self.cfg)
        self.assertTrue(ep["lines"][0]["text"].startswith("2:47"))
        self.assertNotIn("Not enough votes", " ".join(ep["narration"]))

    def test_first_comment_is_english_and_voting_is_real(self):
        ep=engine.build_episode(self.state("store_sound"),self.story,self.cfg)
        self.assertTrue(ep["vote"])
        self.assertIn("YOUR CHOICE", ep["first_comment"])
        self.assertNotIn("VOTE KARO", ep["first_comment"])
        ep_story=engine.build_episode(self.state("intro"),self.story,self.cfg)
        self.assertIsNone(ep_story["first_comment"])

    def test_fallback_still_resolves_story_without_misleading_recap(self):
        state=self.state("store_sound", {
            "node":"store_sound","vote":True,"closed":False,
            "kind":"vote"
        })
        state["node"]="store_sound"
        res=engine.advance(state,self.story,self.cfg,votes={})
        self.assertTrue(res["fallback"])
        self.assertIsNone(engine.recap_line(res))
        self.assertIn(state["node"],self.story["arcs"]["road"]["nodes"])


if __name__=="__main__":
    unittest.main()
