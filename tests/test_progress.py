from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gamewalk_helper.models import GuideStepCandidate, Observation
from gamewalk_helper.progress import ProgressEngine


class ProgressEngineTests(unittest.TestCase):
    def test_returns_definitive_when_score_is_clear(self) -> None:
        engine = ProgressEngine(strong_threshold=0.6, margin_threshold=0.1, max_suggestions=2)
        observation = Observation(
            game_id="TestGame",
            session_id=1,
            timestamp=datetime.now(timezone.utc),
            task_text="前往村庄并寻找铁匠",
            task_confidence=0.9,
            cv_labels=["quest_marker"],
            frame_hash="abc",
        )
        candidates = [
            GuideStepCandidate(
                state_id="find_smith",
                action_text="去村庄铁匠铺对话。",
                text_keywords=["村庄", "铁匠"],
                cv_keywords=["quest_marker"],
                history_prior=0.7,
                priority=20,
            ),
            GuideStepCandidate(
                state_id="go_forest",
                action_text="前往森林入口。",
                text_keywords=["森林"],
                cv_keywords=["enemy_alert"],
                history_prior=0.2,
                priority=5,
            ),
        ]
        decision = engine.evaluate(observation, candidates, previous_state_id="find_smith")
        self.assertTrue(decision.definitive)
        self.assertIsNotNone(decision.primary)
        assert decision.primary is not None
        self.assertEqual(decision.primary.candidate.state_id, "find_smith")

    def test_returns_alternatives_when_ambiguous(self) -> None:
        engine = ProgressEngine(strong_threshold=0.8, margin_threshold=0.2, max_suggestions=2)
        observation = Observation(
            game_id="TestGame",
            session_id=2,
            timestamp=datetime.now(timezone.utc),
            task_text="去主城找商人",
            task_confidence=0.85,
            cv_labels=[],
            frame_hash="def",
        )
        candidates = [
            GuideStepCandidate(
                state_id="find_vendor_a",
                action_text="前往主城东区寻找商人。",
                text_keywords=["主城", "商人"],
                history_prior=0.4,
                priority=10,
            ),
            GuideStepCandidate(
                state_id="find_vendor_b",
                action_text="前往主城市场寻找商人。",
                text_keywords=["主城", "商人"],
                history_prior=0.35,
                priority=9,
            ),
        ]
        decision = engine.evaluate(observation, candidates, previous_state_id=None)
        self.assertFalse(decision.definitive)
        self.assertGreaterEqual(len(decision.alternatives), 1)


if __name__ == "__main__":
    unittest.main()

