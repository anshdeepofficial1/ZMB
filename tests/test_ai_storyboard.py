import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from ai_storyboard import build_prompt

class AIStoryboardPromptTests(unittest.TestCase):
    def test_cinematic_vertical_prompt_keeps_character_continuity(self):
        prompt=build_prompt({"season":1,"day":2},{"text":"Max hears movement behind the door.",
          "shot":{"place":"gas_station","beat":"door_shadow","mood":"danger","time":"night"}})
        self.assertIn("9:16",prompt)
        self.assertIn("Max",prompt)
        self.assertIn("Biscuit",prompt)
        self.assertIn("no written text",prompt.lower())
        self.assertIn("door shadow",prompt.lower())

if __name__=="__main__":unittest.main()
