import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ai_video import build_video_prompt

class AIVideoPromptTests(unittest.TestCase):
    def test_prompt_requires_real_motion_and_vertical_continuity(self):
        prompt = build_video_prompt(
            {"season": 1, "day": 3},
            {"text": "Max runs to the gas station as Biscuit follows.",
             "shot": {"place": "gas_station", "cast": [["max", "run"], ["biscuit", "follow"]],
                      "cam": "push", "time": "night", "mood": "tense"}},
            6,
        )
        self.assertIn("actual moving video", prompt.lower())
        self.assertIn("9:16", prompt)
        self.assertIn("Max", prompt)
        self.assertIn("Biscuit", prompt)
        self.assertIn("single shot", prompt.lower())
        self.assertIn("6 seconds", prompt)

if __name__ == "__main__":
    unittest.main()
