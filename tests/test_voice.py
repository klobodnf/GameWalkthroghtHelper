from __future__ import annotations

from pathlib import Path
import tempfile
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gamewalk_helper.db import Database
from gamewalk_helper.voice import VoiceCoach, clamp_volume


class FakeSpeaker:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.volumes: list[float] = []

    def say(self, text: str) -> None:
        self.messages.append(text)

    def set_volume(self, value: float) -> float:
        self.volumes.append(value)
        return value


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
                forced = coach.try_speak("TestGame", "下一步去村庄", ignore_cooldown=True)

                self.assertTrue(first)
                self.assertFalse(second)
                self.assertTrue(third)
                self.assertTrue(forced)
                self.assertEqual(len(speaker.messages), 3)
                self.assertAlmostEqual(speaker.volumes[-1], 1.0, places=6)

                updated = coach.set_volume(0.35)
                self.assertAlmostEqual(updated, 0.35, places=6)
                self.assertAlmostEqual(coach.get_volume(), 0.35, places=6)
                self.assertAlmostEqual(speaker.volumes[-1], 0.35, places=6)
            finally:
                db.close()

    def test_clamp_volume(self) -> None:
        self.assertEqual(clamp_volume(-1.0), 0.0)
        self.assertEqual(clamp_volume(2.0), 1.0)
        self.assertAlmostEqual(clamp_volume(0.62), 0.62, places=6)


if __name__ == "__main__":
    unittest.main()
