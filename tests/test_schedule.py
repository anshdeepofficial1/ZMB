from datetime import datetime, timedelta
import unittest

from common import IST
from run_cycle import _publish_target, _parse_ist_timestamp


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


if __name__ == "__main__":
    unittest.main()
