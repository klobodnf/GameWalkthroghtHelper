from __future__ import annotations

from pathlib import Path
import tempfile
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gamewalk_helper.db import Database
from gamewalk_helper.voice import VoiceCoach


class FakeSpeaker:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def say(self, text: str) -> None:
        self.messages.append(text)


class VoiceCoachTests(unittest.TestCase):
    def test_cooldown_blocks_repeated_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "voice.db")
            db = Database(db_path)
            try:
                db.init_schema()
                speaker = FakeSpeaker()
                coach = VoiceCoach(db=db, cooldown_seconds=60, speaker=speaker)

                first = coach.try_speak("TestGame", "下一步去村庄")
                second = coach.try_speak("TestGame", "下一步  去村庄")
                third = coach.try_speak("TestGame", "现在打开背包")

                self.assertTrue(first)
                self.assertFalse(second)
                self.assertTrue(third)
                self.assertEqual(len(speaker.messages), 2)
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
