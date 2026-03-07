from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gamewalk_helper.stabilizer import ProgressStabilizer


class ProgressStabilizerTests(unittest.TestCase):
    def test_requires_repeated_hits_before_becoming_stable(self) -> None:
        stabilizer = ProgressStabilizer(window_size=5, stable_hits=3)
        first = stabilizer.update(state_id="state_a", hint_text="hint a", confidence=0.6)
        second = stabilizer.update(state_id="state_b", hint_text="hint b", confidence=0.8)
        third = stabilizer.update(state_id="state_a", hint_text="hint a2", confidence=0.7)
        fourth = stabilizer.update(state_id="state_a", hint_text="hint a3", confidence=0.9)

        self.assertFalse(first.stable)
        self.assertFalse(second.stable)
        self.assertFalse(third.stable)
        self.assertTrue(fourth.stable)
        self.assertEqual(fourth.state_id, "state_a")
        self.assertEqual(fourth.hits, 3)
        self.assertEqual(fourth.hint_text, "hint a3")

    def test_prefers_state_with_higher_average_confidence_on_tie(self) -> None:
        stabilizer = ProgressStabilizer(window_size=4, stable_hits=2)
        stabilizer.update(state_id="state_a", hint_text="a1", confidence=0.5)
        stabilizer.update(state_id="state_b", hint_text="b1", confidence=0.9)
        stabilizer.update(state_id="state_a", hint_text="a2", confidence=0.5)
        result = stabilizer.update(state_id="state_b", hint_text="b2", confidence=0.8)

        self.assertEqual(result.state_id, "state_b")
        self.assertTrue(result.stable)
        self.assertGreaterEqual(result.confidence, 0.85)


if __name__ == "__main__":
    unittest.main()
