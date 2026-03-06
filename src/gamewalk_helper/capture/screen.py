from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ScreenFrame:
    image: Any
    hash_value: str


class ScreenCapture:
    def __init__(self, monitor_index: int = 1) -> None:
        self.monitor_index = monitor_index

    def grab(self) -> ScreenFrame | None:
        try:
            import hashlib
            from PIL import Image  # type: ignore
            import mss  # type: ignore
        except Exception:
            return None

        with mss.mss() as sct:
            monitors = sct.monitors
            if self.monitor_index >= len(monitors):
                return None
            raw = sct.grab(monitors[self.monitor_index])
            image = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            hash_value = hashlib.sha1(image.tobytes()).hexdigest()
            return ScreenFrame(image=image, hash_value=hash_value)

