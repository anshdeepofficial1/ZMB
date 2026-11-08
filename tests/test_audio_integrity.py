"""No Reel can silently lose its narration or fake timing metadata."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from render import synthesize_voices


class NarrationQualityTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {"voice":"en-US-ChristopherNeural", "voice_rate":"+0%",
                    "render":{"gap_seconds":0.4}}
        self.ep = {"lines":[{"text":"The headlights flicker.", "shot":{"place":"highway"}}]}

    def test_failed_tts_aborts_instead_of_creating_silent_audio(self):
        async def failed(*args):
            raise ConnectionError("speech service unreachable")
        with TemporaryDirectory() as tmp, \
             patch("render._tts_line", side_effect=failed), \
             patch("render.time.sleep", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "refusing to render a silent"):
                synthesize_voices(self.cfg, self.ep, Path(tmp), Log=lambda *args: None)
            self.assertFalse((Path(tmp) / "audio" / "l00.wav").exists())

    def test_missing_word_boundaries_aborts_instead_of_fake_subtitles(self):
        async def no_words(_text, _voice, _rate, path):
            path.write_bytes(b"not used because caption check comes first")
            return []
        with TemporaryDirectory() as tmp, patch("render._tts_line", side_effect=no_words):
            with self.assertRaisesRegex(RuntimeError, "no word-level timing"):
                synthesize_voices(self.cfg, self.ep, Path(tmp), Log=lambda *args: None)


if __name__ == "__main__":
    unittest.main()
