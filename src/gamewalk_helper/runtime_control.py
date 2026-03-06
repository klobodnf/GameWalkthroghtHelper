from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Lock


@dataclass(frozen=True, slots=True)
class ControlSnapshot:
    muted: bool
    paused: bool
    detail_level: int


class RuntimeControl:
    def __init__(self, initial_detail_level: int = 1) -> None:
        self._lock = Lock()
        self._muted = False
        self._paused = False
        self._detail_level = _clamp_detail(initial_detail_level)
        self._force_hint = Event()
        self._stop = Event()

    def toggle_mute(self) -> bool:
        with self._lock:
            self._muted = not self._muted
            return self._muted

    def toggle_pause(self) -> bool:
        with self._lock:
            self._paused = not self._paused
            return self._paused

    def cycle_detail(self) -> int:
        with self._lock:
            self._detail_level = (self._detail_level + 1) % 3
            return self._detail_level

    def request_force_hint(self) -> None:
        self._force_hint.set()

    def consume_force_hint(self) -> bool:
        if not self._force_hint.is_set():
            return False
        self._force_hint.clear()
        return True

    def stop(self) -> None:
        self._stop.set()

    def should_stop(self) -> bool:
        return self._stop.is_set()

    def snapshot(self) -> ControlSnapshot:
        with self._lock:
            return ControlSnapshot(
                muted=self._muted,
                paused=self._paused,
                detail_level=self._detail_level,
            )


def _clamp_detail(value: int) -> int:
    if value <= 0:
        return 0
    if value >= 2:
        return 2
    return value

