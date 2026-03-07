from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gamewalk_helper.config import AppConfig, load_config


class ConfigEnvOverrideTests(unittest.TestCase):
    def test_load_config_reads_ai_env_overrides(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "GWH_AI_ADVISOR_ENABLED": "true",
                "GWH_AI_ADVISOR_PROVIDER": "kimi",
                "GWH_AI_ADVISOR_PROTOCOL": "openai_chat",
                "GWH_AI_ADVISOR_API_KEY_ENV": "KIMI_API_KEY",
                "GWH_AI_ADVISOR_MODEL": "moonshot-v1-8k",
                "GWH_AI_ADVISOR_BASE_URL": "https://api.moonshot.cn/v1",
                "GWH_AI_ADVISOR_REQUEST_PATH": "/chat/completions",
                "GWH_AI_ADVISOR_TEMPERATURE": "0.35",
                "GWH_AI_ADVISOR_TIMEOUT_SECONDS": "20",
                "GWH_AI_ADVISOR_MAX_TOKENS": "96",
                "GWH_AI_ADVISOR_COOLDOWN_SECONDS": "30",
            },
            clear=False,
        ):
            config = load_config("config/default.yaml")

        self.assertTrue(config.ai_advisor_enabled)
        self.assertEqual(config.ai_advisor_provider, "kimi")
        self.assertEqual(config.ai_advisor_protocol, "openai_chat")
        self.assertEqual(config.ai_advisor_api_key_env, "KIMI_API_KEY")
        self.assertEqual(config.ai_advisor_model, "moonshot-v1-8k")
        self.assertEqual(config.ai_advisor_base_url, "https://api.moonshot.cn/v1")
        self.assertEqual(config.ai_advisor_request_path, "/chat/completions")
        self.assertEqual(config.ai_advisor_temperature, 0.35)
        self.assertEqual(config.ai_advisor_timeout_seconds, 20)
        self.assertEqual(config.ai_advisor_max_tokens, 96)
        self.assertEqual(config.ai_advisor_cooldown_seconds, 30)

    def test_invalid_env_values_do_not_override(self) -> None:
        baseline = AppConfig()
        with patch.dict(
            "os.environ",
            {
                "GWH_AI_ADVISOR_ENABLED": "maybe",
                "GWH_AI_ADVISOR_TEMPERATURE": "invalid",
                "GWH_AI_ADVISOR_TIMEOUT_SECONDS": "invalid",
            },
            clear=False,
        ):
            config = load_config(None)

        self.assertEqual(config.ai_advisor_enabled, baseline.ai_advisor_enabled)
        self.assertEqual(config.ai_advisor_temperature, baseline.ai_advisor_temperature)
        self.assertEqual(config.ai_advisor_timeout_seconds, baseline.ai_advisor_timeout_seconds)


if __name__ == "__main__":
    unittest.main()
