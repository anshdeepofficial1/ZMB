from datetime import datetime, timedelta
from pathlib import Path
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from common import IST
from run_cycle import _publish_target, _parse_ist_timestamp
from animate import narrative_beat_layer, chunk_words

ROOT = Path(__file__).resolve().parents[1]


class PublishScheduleTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {
            "publish_time_ist": "20:00",
            "publish_every_hours": 24,
            "publish_prepare_hours": 1,
        }

    def ts(self, day, hour, minute=0, second=0):
        return datetime(2026, 10, day, hour, minute, second, tzinfo=IST)

    def test_daily_reel_is_not_prepared_before_the_last_hour(self):
        state = {"history": [{"posted_at_ist": "2026-10-25T20:00:00+05:30"}]}
        self.assertIsNone(_publish_target(state, self.cfg, self.ts(26, 18, 59), False))

    def test_preparation_opens_at_23_hours_and_targets_24_hours(self):
        state = {"history": [{"posted_at_ist": "2026-10-25T20:00:00+05:30"}]}
        now = self.ts(26, 19, 0)
        target = _publish_target(state, self.cfg, now, False)
        self.assertEqual(target, self.ts(26, 20, 0))
        self.assertEqual(target - self.ts(25, 20, 0), timedelta(hours=24))

    def test_late_run_does_not_post_again_or_reset_the_interval(self):
        state = {"history": [{"posted_at_ist": "2026-10-25T20:00:00+05:30"}]}
        now = self.ts(26, 20, 5)
        self.assertEqual(_publish_target(state, self.cfg, now, False), now)

    def test_legacy_state_uses_configured_publish_time(self):
        state = {"history": [{"posted_ist_date": "2026-10-25"}]}
        now = self.ts(26, 19, 0)
        self.assertEqual(_publish_target(state, self.cfg, now, False), self.ts(26, 20, 0))

    def test_first_post_uses_configured_window_not_random_checkpoint(self):
        state = {"history": []}
        self.assertIsNone(_publish_target(state, self.cfg, self.ts(26, 18, 59), False))
        self.assertEqual(
            _publish_target(state, self.cfg, self.ts(26, 19, 0), False),
            self.ts(26, 20, 0),
        )

    def test_force_publish_is_immediate(self):
        now = self.ts(26, 12, 34, 56)
        self.assertEqual(_publish_target({"history": []}, self.cfg, now, True), now)

    def test_timestamp_parser_respects_ist_offset(self):
        parsed = _parse_ist_timestamp("2026-10-25T20:00:00+05:30", IST)
        self.assertEqual(parsed, self.ts(25, 20, 0))


class NarrativeVisualBeatTests(unittest.TestCase):
    def test_breakdown_scene_has_car_driver_and_engine_smoke(self):
        svg = narrative_beat_layer({"beat": "breakdown"}, 1.25)
        self.assertIn("ENGINE FAILURE", svg)
        self.assertIn("zmb-break-window", svg)
        self.assertIn("M 788 1257", svg)
        self.assertIn("translate(72 1515)", svg)

    def test_interior_scene_is_a_real_cabin_composition(self):
        svg = narrative_beat_layer({"beat": "car_interior"}, 2.0)
        self.assertIn("STALLED", svg)
        self.assertIn("translate(425 1492)", svg)
        self.assertIn("translate(692 1454)", svg)
        self.assertIn("STALLED", svg)

    def test_backpack_is_explicitly_rendered(self):
        svg = narrative_beat_layer({"beat": "backpack_exit"}, 0.8)
        self.assertIn("#7b3f2b", svg)
        self.assertIn("M 342 1028", svg)
        self.assertIn("M 349 1020", svg)

    def test_choice_teaser_has_both_real_story_choices(self):
        svg = narrative_beat_layer({"beat": "choice_teaser"}, 1.1)
        self.assertIn(">RUN</text>", svg)
        self.assertIn(">CHECK</text>", svg)
        self.assertIn("COMMENT ON TOMORROW", svg)





    def test_caption_chunks_stop_at_sentence_punctuation(self):
        class DummyTexts:
            def w(self, value, size):
                return len(value) * 10

        # Simulate Edge TTS WordBoundary, which commonly drops punctuation.
        tokens = ["RUN", "to", "escape", "or", "CHECK", "the", "door",
                  "Follow", "and", "vote", "on", "tomorrow's", "Reel"]
        words = [{"w": word, "start": i * 0.2, "end": i * 0.2 + 0.18}
                 for i, word in enumerate(tokens)]
        source = "RUN to escape or CHECK the door? Follow and vote on tomorrow's Reel."
        chunks = chunk_words(words, DummyTexts(), 54, max_w=1200, max_words=7,
                             source_text=source)
        self.assertEqual([x["w"] for x in chunks[0]["words"]],
                         ["RUN", "to", "escape", "or", "CHECK", "the", "door?"])
        self.assertEqual([x["w"] for x in chunks[1]["words"]],
                         ["Follow", "and", "vote", "on", "tomorrow's", "Reel."])

    def test_station_door_has_a_moving_shadow_and_visible_door_frame(self):
        svg = narrative_beat_layer({"beat": "door_shadow"}, 1.4)
        self.assertIn('x="738" y="894"', svg)
        self.assertIn("#05090f", svg)
        self.assertIn("flicker", svg.lower()) if "flicker" in svg.lower() else self.assertIn("OPEN 24 HOURS", svg)

    def test_intro_narration_has_matching_visual_beats(self):
        scenarios = json.loads((ROOT / "content" / "scenarios.json").read_text(encoding="utf-8"))
        lines = scenarios["arcs"]["road"]["nodes"]["intro"]["lines"]
        beats = [line.get("shot", {}).get("beat") for line in lines]
        self.assertEqual(
            beats,
            ["breakdown", "car_interior", "spot_station", "backpack_exit", "door_shadow", "choice_teaser"],
        )
        self.assertIn("engine", lines[0]["text"].lower())
        self.assertIn("backpack", lines[3]["text"].lower())


if __name__ == "__main__":
    unittest.main()
