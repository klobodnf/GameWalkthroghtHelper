from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gamewalk_helper.ai_advisor import AIHintAdvisor, AdvisorContext, list_supported_providers


class AIHintAdvisorTests(unittest.TestCase):
    def test_returns_local_hint_when_disabled(self) -> None:
        advisor = AIHintAdvisor(enabled=False)
        hint = advisor.suggest(
            AdvisorContext(
                game_id="steam_1",
                base_hint="下一步：前往村口。",
                task_text="前往村口",
                confidence=0.9,
                state_id="state_1",
            )
        )
        self.assertEqual(hint, "下一步：前往村口。")

    def test_low_confidence_local_hint_is_prefixed(self) -> None:
        advisor = AIHintAdvisor(enabled=False)
        hint = advisor.suggest(
            AdvisorContext(
                game_id="steam_1",
                base_hint="检查地图上的目标点。",
                task_text="",
                confidence=0.2,
                state_id=None,
            )
        )
        self.assertTrue(hint.startswith("低置信度建议："))

    def test_remote_result_is_cached_during_cooldown(self) -> None:
        advisor = AIHintAdvisor(
            enabled=True,
            api_key_env="GWH_TEST_KEY",
            cooldown_seconds=600,
        )
        ctx = AdvisorContext(
            game_id="steam_2",
            base_hint="去主城找铁匠。",
            task_text="去主城找铁匠",
            confidence=0.85,
            state_id="state_blacksmith",
        )
        with patch.dict("os.environ", {"GWH_TEST_KEY": "dummy"}, clear=False):
            with patch.object(advisor, "_call_remote", return_value="先传送到主城。") as mocked:
                first = advisor.suggest(ctx)
                second = advisor.suggest(ctx)

        self.assertEqual(first, "先传送到主城。")
        self.assertEqual(second, "先传送到主城。")
        self.assertEqual(mocked.call_count, 1)

    def test_kimi_provider_applies_preset_defaults(self) -> None:
        advisor = AIHintAdvisor(enabled=False, provider="kimi")
        self.assertEqual(advisor.provider, "kimi")
        self.assertEqual(advisor.base_url, "https://api.moonshot.cn/v1")
        self.assertEqual(advisor.model, "moonshot-v1-8k")
        self.assertEqual(advisor.api_key_env, "KIMI_API_KEY")
        self.assertEqual(advisor.protocol, "openai_chat")

    def test_ollama_provider_can_run_without_api_key(self) -> None:
        advisor = AIHintAdvisor(enabled=True, provider="ollama", cooldown_seconds=600)
        ctx = AdvisorContext(
            game_id="local_game",
            base_hint="前往下一个区域。",
            task_text="",
            confidence=0.9,
            state_id="state_local",
        )
        with patch.dict("os.environ", {}, clear=True):
            with patch.object(advisor, "_call_remote", return_value="本地模型提示。") as mocked:
                hint = advisor.suggest(ctx)
        self.assertEqual(hint, "本地模型提示。")
        self.assertEqual(mocked.call_count, 1)

    def test_supported_provider_list_contains_mainstream_options(self) -> None:
        providers = set(list_supported_providers())
        self.assertTrue({"openai", "kimi", "deepseek", "qwen", "zhipu", "anthropic", "gemini", "ollama"}.issubset(providers))


if __name__ == "__main__":
    unittest.main()
