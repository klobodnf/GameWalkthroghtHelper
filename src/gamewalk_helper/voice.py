from __future__ import annotations

import hashlib
import re
from threading import Lock

from .db import Database


class Speaker:
    def __init__(self, volume: float = 1.0) -> None:
        self._volume = clamp_volume(volume)
        self._lock = Lock()
        self._engine = None

    def set_volume(self, volume: float) -> float:
        clamped = clamp_volume(volume)
        with self._lock:
            self._volume = clamped
            if self._engine is not None:
                try:
                    self._engine.setProperty("volume", clamped)
                except Exception:
                    pass
        return clamped

    def get_volume(self) -> float:
        with self._lock:
            return self._volume

    def say(self, text: str) -> None:
        with self._lock:
            engine = self._get_engine_locked()
            if engine is None:
                print(f"[VoiceFallback] {text}")
                return
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception:
                self._engine = None
                print(f"[VoiceFallback] {text}")

    def _get_engine_locked(self):  # type: ignore[no-untyped-def]
        if self._engine is not None:
            return self._engine
        try:
            import pyttsx3  # type: ignore

            engine = pyttsx3.init()
            engine.setProperty("volume", self._volume)
            self._engine = engine
            return self._engine
        except Exception:
            return None


class VoiceCoach:
    def __init__(
        self,
        db: Database,
        cooldown_seconds: int = 30,
        speaker: Speaker | None = None,
        voice_volume: float = 1.0,
    ) -> None:
        self.db = db
        self.cooldown_seconds = cooldown_seconds
        self.speaker = speaker or Speaker(volume=voice_volume)
        self._volume_lock = Lock()
        self._volume = clamp_volume(voice_volume)
        self.set_volume(self._volume)

    def set_volume(self, volume: float) -> float:
        clamped = clamp_volume(volume)
        with self._volume_lock:
            self._volume = clamped
            set_volume = getattr(self.speaker, "set_volume", None)
            if callable(set_volume):
                set_volume(clamped)
        return clamped

    def get_volume(self) -> float:
        with self._volume_lock:
            return self._volume

    def try_speak(self, game_id: str, text: str, ignore_cooldown: bool = False) -> bool:
        normalized = _normalize(text)
        voice_key = _voice_key(game_id, normalized)
        if not ignore_cooldown and not self.db.should_speak(voice_key):
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


def clamp_volume(value: float) -> float:
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return float(value)

