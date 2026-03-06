from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gamewalk_helper.models import GuideStepCandidate, ProgressDecision, StateScore
from gamewalk_helper.pipeline import _format_hint_text


class HintFormatTests(unittest.TestCase):
    def test_definitive_levels(self) -> None:
        candidate = GuideStepCandidate(
            state_id="s1",
            action_text="前往村庄铁匠铺",
            source_url="https://example.com/guide",
        )
        score = StateScore(
            candidate=candidate,
            total=0.9,
            text_match=0.9,
            cv_match=0.6,
            temporal=1.0,
            history_prior=0.7,
        )
        decision = ProgressDecision(definitive=True, primary=score, alternatives=[])
        self.assertEqual(_format_hint_text(decision, detail_level=0), "前往村庄铁匠铺")
        self.assertIn("下一步", _format_hint_text(decision, detail_level=1))
        self.assertIn("参考", _format_hint_text(decision, detail_level=2))

    def test_ambiguous_levels(self) -> None:
        c1 = GuideStepCandidate(state_id="a", action_text="去东门找商人")
        c2 = GuideStepCandidate(state_id="b", action_text="去市场找商人")
        s1 = StateScore(candidate=c1, total=0.6, text_match=0.7, cv_match=0.0, temporal=0.4, history_prior=0.3)
        s2 = StateScore(candidate=c2, total=0.58, text_match=0.68, cv_match=0.0, temporal=0.4, history_prior=0.3)
        decision = ProgressDecision(definitive=False, primary=s1, alternatives=[s2])
        self.assertIn("候选步骤", _format_hint_text(decision, detail_level=1))
        self.assertIn("建议按任务面板再确认一次", _format_hint_text(decision, detail_level=2))


if __name__ == "__main__":
    unittest.main()

