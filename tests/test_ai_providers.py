import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ai_providers


class LocalAIProviderTests(TestCase):
    def setUp(self):
        self.episode = {
            "season": 1, "day": 2, "node": "motel", "kind": "vote",
            "hook": "Something is outside.", "subtitle": "Motel",
            "lines": [
                {"text": "Max hears a sound.", "shot": {"place": "motel", "beat": "listen", "mood": "tense", "time": "night", "cam": "push", "cast": [["max", "idle"]]}},
                {"text": "Biscuit growls.", "shot": {"place": "motel", "beat": "dog growl", "mood": "fear", "time": "night", "cam": "medium"}},
            ],
            "choices": [{"key": "run", "text": "Run", "next": "road"}, {"key": "hide", "text": "Hide", "next": "room"}],
            "caption": "unchanged",
        }

    def test_disabled_mode_keeps_authored_lines(self):
        with patch.dict("os.environ", {"ZMB_LOCAL_AI_ENABLED": "0"}):
            result = ai_providers.rewrite_episode(self.episode, lambda *_: None)
        self.assertEqual(result["lines"], self.episode["lines"])
        self.assertEqual(result["choices"], self.episode["choices"])
        self.assertEqual(result["ai_story"]["status"], "disabled")

    def test_local_rewrite_preserves_choices_and_renderer_fields(self):
        generated = {"lines": [
            {"text": "Max freezes as a shadow crosses the motel door.", "shot": {"place": "motel", "beat": "shadow crosses door", "mood": "danger", "time": "night", "cam": "creep", "cast": [["max", "sneak"]], "fx": "fog"}},
            {"text": "Biscuit bares his teeth at the door.", "shot": {"place": "motel", "beat": "dog warning", "mood": "fear", "time": "night", "cam": "push"}},
        ]}
        fake_llm = Mock()
        fake_llm.create_chat_completion.return_value = {"choices": [{"message": {"content": json.dumps(generated)}}]}
        fake_module = SimpleNamespace(Llama=Mock(return_value=fake_llm))
        with patch.dict(sys.modules, {"llama_cpp": fake_module}), patch.object(ai_providers, "_model_path", return_value=Path("/tmp/model.gguf")):
            result = ai_providers.rewrite_episode(self.episode, lambda *_: None)
        self.assertEqual(len(result["lines"]), 2)
        self.assertEqual(result["choices"], self.episode["choices"])
        self.assertEqual(result["caption"], "unchanged")
        self.assertEqual(result["lines"][0]["shot"]["cast"], [["max", "sneak"]])
        self.assertEqual(result["lines"][0]["shot"]["fx"], "fog")
        self.assertEqual(result["ai_story"]["provider"], "local-llama.cpp")
        self.assertEqual(result["ai_story"]["status"], "success")

    def test_local_model_failure_is_marked_and_keeps_authored_lines(self):
        with patch.dict(sys.modules, {"llama_cpp": SimpleNamespace(Llama=Mock(side_effect=RuntimeError("no model")))}), patch.object(ai_providers, "_model_path", return_value=Path("/tmp/model.gguf")):
            result = ai_providers.rewrite_episode(self.episode, lambda *_: None)
        self.assertEqual(result["lines"], self.episode["lines"])
        self.assertEqual(result["ai_story"]["status"], "fallback")
        self.assertEqual(result["ai_story"]["error"], "RuntimeError")

    def test_invalid_line_count_is_rejected(self):
        with self.assertRaises(ValueError):
            ai_providers._validate_lines(self.episode, [{"text": "only one", "shot": {"place": "motel", "beat": "x"}}])


if __name__ == "__main__":
    main()
