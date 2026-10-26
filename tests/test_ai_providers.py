import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ai_providers import rewrite_episode


class AIProviderValidationTests(unittest.TestCase):
    def setUp(self):
        self.episode = {
            "season": 1, "day": 3, "node": "intro", "kind": "vote",
            "hook": "A door slams.", "subtitle": "Choose",
            "lines": [
                {"text": "Max hears a sound.", "shot": {"place": "motel", "beat": "sound", "mood": "tense", "time": "night", "cam": "closeup"}},
                {"text": "Biscuit growls.", "shot": {"place": "motel", "beat": "dog growl", "mood": "fear", "time": "night", "cam": "medium"}},
            ],
            "choices": [{"key": "run", "text": "Run", "next": "road"}, {"key": "hide", "text": "Hide", "next": "room"}],
            "caption": "unchanged",
        }

    def test_no_token_keeps_authored_lines(self):
        with patch.dict(os.environ, {"HF_TOKEN": ""}):
            result = rewrite_episode(self.episode, lambda *_: None)
        self.assertEqual(result["lines"], self.episode["lines"])
        self.assertEqual(result["choices"], self.episode["choices"])

    def test_rewrite_preserves_line_count_and_choices(self):
        content = json.dumps({"lines": [
            {"text": "Max freezes as a shadow moves.", "shot": {"place": "motel", "beat": "moving shadow", "mood": "tense", "time": "night", "cam": "closeup"}},
            {"text": "Biscuit bares his teeth at the door.", "shot": {"place": "motel", "beat": "dog warning", "mood": "fear", "time": "night", "cam": "medium"}},
        ]})
        response = Mock(status_code=200)
        response.json.return_value = {"choices": [{"message": {"content": content}}]}
        with patch.dict(os.environ, {"HF_TOKEN": "test-token"}), patch("ai_providers.requests.post", return_value=response):
            result = rewrite_episode(self.episode, lambda *_: None)
        self.assertEqual(len(result["lines"]), 2)
        self.assertEqual(result["choices"], self.episode["choices"])
        self.assertEqual(result["caption"], "unchanged")
        self.assertEqual(result["ai_story"]["status"], "success")

    def test_malformed_model_output_fails_closed(self):
        response = Mock(status_code=200)
        response.json.return_value = {"choices": [{"message": {"content": "{bad json"}}]}
        with patch.dict(os.environ, {"HF_TOKEN": "test-token"}), patch("ai_providers.requests.post", return_value=response):
            with self.assertRaises(RuntimeError):
                rewrite_episode(self.episode, lambda *_: None)


if __name__ == "__main__":
    unittest.main()
