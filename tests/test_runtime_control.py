from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gamewalk_helper.runtime_control import RuntimeControl


class RuntimeControlTests(unittest.TestCase):
    def test_toggle_and_snapshot(self) -> None:
        control = RuntimeControl(initial_detail_level=1)
        first = control.snapshot()
        self.assertFalse(first.muted)
        self.assertFalse(first.paused)
        self.assertEqual(first.detail_level, 1)

        control.toggle_mute()
        control.toggle_pause()
        level = control.cycle_detail()
        second = control.snapshot()
        self.assertTrue(second.muted)
        self.assertTrue(second.paused)
        self.assertEqual(level, 2)
        self.assertEqual(second.detail_level, 2)

    def test_force_hint_flag_is_consumed_once(self) -> None:
        control = RuntimeControl()
        self.assertFalse(control.consume_force_hint())
        control.request_force_hint()
        self.assertTrue(control.consume_force_hint())
        self.assertFalse(control.consume_force_hint())

    def test_stop_flag(self) -> None:
        control = RuntimeControl()
        self.assertFalse(control.should_stop())
        control.stop()
        self.assertTrue(control.should_stop())


if __name__ == "__main__":
    unittest.main()

