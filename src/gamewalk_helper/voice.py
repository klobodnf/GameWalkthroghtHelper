from __future__ import annotations

import hashlib
import re

from .db import Database


class Speaker:
    def say(self, text: str) -> None:
        try:
            import pyttsx3  # type: ignore

            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception:
            print(f"[VoiceFallback] {text}")


class VoiceCoach:
    def __init__(self, db: Database, cooldown_seconds: int = 30, speaker: Speaker | None = None) -> None:
        self.db = db
        self.cooldown_seconds = cooldown_seconds
        self.speaker = speaker or Speaker()

    def try_speak(self, game_id: str, text: str) -> bool:
        normalized = _normalize(text)
        voice_key = _voice_key(game_id, normalized)
        if not self.db.should_speak(voice_key):
            return False
        self.speaker.say(text)
        self.db.mark_spoken(
            voice_key=voice_key,
            game_id=game_id,
            message=text,
            cooldown_seconds=self.cooldown_seconds,
        )
        return True


def _normalize(text: str) -> str:
    lowered = text.strip().lower()
    return re.sub(r"\s+", "", lowered)


def _voice_key(game_id: str, normalized_text: str) -> str:
    digest = hashlib.sha1(normalized_text.encode("utf-8")).hexdigest()
    return f"{game_id}:{digest}"
