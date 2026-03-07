from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gamewalk_helper.voice_input import parse_voice_command


class VoiceInputCommandTests(unittest.TestCase):
    def test_parse_chinese_force_hint(self) -> None:
        command = parse_voice_command("请给我下一步提示")
        self.assertEqual(command, "force_hint")

    def test_parse_english_pause_with_wake_word(self) -> None:
        command = parse_voice_command("assistant pause", wake_word="assistant")
        self.assertEqual(command, "pause")

    def test_requires_wake_word_when_configured(self) -> None:
        command = parse_voice_command("pause", wake_word="assistant")
        self.assertIsNone(command)

    def test_parse_unmute_before_mute(self) -> None:
        command = parse_voice_command("取消静音")
        self.assertEqual(command, "unmute")


if __name__ == "__main__":
    unittest.main()
