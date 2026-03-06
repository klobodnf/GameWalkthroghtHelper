from __future__ import annotations

from pathlib import Path
from typing import Any


class CvMatcher:
    def __init__(self, template_dir: str, threshold: float = 0.8) -> None:
        self.template_dir = Path(template_dir)
        self.threshold = threshold
        self._templates: dict[str, Any] = {}
        self._load_templates()

    def _load_templates(self) -> None:
        if not self.template_dir.exists():
            return
        try:
            import cv2  # type: ignore
        except Exception:
            return
        for file_path in self.template_dir.glob("*.png"):
            image = cv2.imread(str(file_path), cv2.IMREAD_GRAYSCALE)
            if image is not None:
                self._templates[file_path.stem] = image

    def match_labels(self, frame_image: Any) -> list[str]:
        if not self._templates:
            return []
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore
        except Exception:
            return []

        gray = cv2.cvtColor(np.array(frame_image), cv2.COLOR_RGB2GRAY)
        labels: list[str] = []
        for label, template in self._templates.items():
            result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_score, _, _ = cv2.minMaxLoc(result)
            if max_score >= self.threshold:
                labels.append(label)
        return labels

