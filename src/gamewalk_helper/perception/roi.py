from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ocr import OcrEngine, OcrResult


DEFAULT_CANDIDATES: list[tuple[float, float, float, float]] = [
    (0.02, 0.05, 0.42, 0.28),  # top-left mission panel
    (0.56, 0.05, 0.42, 0.28),  # top-right mission panel
    (0.18, 0.03, 0.64, 0.22),  # center-top subtitle/task
    (0.04, 0.55, 0.48, 0.22),  # left-bottom hints
    (0.48, 0.55, 0.48, 0.22),  # right-bottom hints
]

TASK_KEYWORDS = {
    "任务",
    "目标",
    "前往",
    "对话",
    "击败",
    "收集",
    "进入",
    "quest",
    "objective",
    "mission",
    "go to",
    "talk",
    "defeat",
    "collect",
    "enter",
}


@dataclass(slots=True)
class PixelRoi:
    x: int
    y: int
    width: int
    height: int

    def as_text(self) -> str:
        return f"{self.x},{self.y},{self.width},{self.height}"


@dataclass(slots=True)
class RoiSelection:
    roi: PixelRoi
    cropped_image: Any
    ocr_result: OcrResult
    score: float


class TaskRoiLocator:
    def __init__(
        self,
        auto_detect: bool = True,
        manual_roi: dict[str, int] | None = None,
        min_score: float = 0.25,
        switch_margin: float = 0.08,
        sticky_bonus: float = 0.06,
        candidate_regions: list[tuple[float, float, float, float]] | None = None,
    ) -> None:
        self.auto_detect = auto_detect
        self.manual_roi = manual_roi
        self.min_score = min_score
        self.switch_margin = switch_margin
        self.sticky_bonus = sticky_bonus
        self.candidate_regions = candidate_regions or DEFAULT_CANDIDATES
        self._last_roi: PixelRoi | None = None
        self._last_score: float = 0.0

    def locate(self, image: Any, ocr_engine: OcrEngine) -> RoiSelection:
        if self.manual_roi:
            roi = self._from_manual(image, self.manual_roi)
            cropped = image.crop((roi.x, roi.y, roi.x + roi.width, roi.y + roi.height))
            result = ocr_engine.extract_task_text(cropped)
            score = _score_ocr(result)
            self._remember(roi, score)
            return RoiSelection(roi=roi, cropped_image=cropped, ocr_result=result, score=score)

        if not self.auto_detect:
            full = PixelRoi(0, 0, image.width, image.height)
            result = ocr_engine.extract_task_text(image)
            score = _score_ocr(result)
            self._remember(full, score)
            return RoiSelection(roi=full, cropped_image=image, ocr_result=result, score=score)

        best_selection = self._find_best_candidate(image, ocr_engine)
        if best_selection.score < self.min_score:
            return self._fallback_to_previous_or_full(image, ocr_engine, best_selection)
        self._remember(best_selection.roi, best_selection.score)
        return best_selection

    def _find_best_candidate(self, image: Any, ocr_engine: OcrEngine) -> RoiSelection:
        candidates: list[RoiSelection] = []
        for norm in self.candidate_regions:
            roi = _norm_to_pixel(norm, image.width, image.height)
            cropped = image.crop((roi.x, roi.y, roi.x + roi.width, roi.y + roi.height))
            ocr = ocr_engine.extract_task_text(cropped)
            score = _score_ocr(ocr)
            if self._last_roi and _same_roi(roi, self._last_roi):
                score += self.sticky_bonus
            candidates.append(RoiSelection(roi=roi, cropped_image=cropped, ocr_result=ocr, score=min(1.0, score)))

        candidates.sort(key=lambda item: item.score, reverse=True)
        top = candidates[0]
        if self._last_roi and not _same_roi(top.roi, self._last_roi) and self._last_score > 0:
            last_candidate = next((item for item in candidates if _same_roi(item.roi, self._last_roi)), None)
            if last_candidate and (top.score - last_candidate.score) < self.switch_margin:
                return last_candidate
        return top

    def _fallback_to_previous_or_full(self, image: Any, ocr_engine: OcrEngine, best: RoiSelection) -> RoiSelection:
        if self._last_roi and self._last_score >= self.min_score * 0.7:
            roi = self._last_roi
            cropped = image.crop((roi.x, roi.y, roi.x + roi.width, roi.y + roi.height))
            ocr = ocr_engine.extract_task_text(cropped)
            score = _score_ocr(ocr)
            self._remember(roi, score)
            return RoiSelection(roi=roi, cropped_image=cropped, ocr_result=ocr, score=score)
        full = PixelRoi(0, 0, image.width, image.height)
        ocr = ocr_engine.extract_task_text(image)
        score = _score_ocr(ocr)
        self._remember(full, score)
        return RoiSelection(roi=full, cropped_image=image, ocr_result=ocr, score=score)

    def _from_manual(self, image: Any, payload: dict[str, int]) -> PixelRoi:
        x = int(payload.get("x", 0))
        y = int(payload.get("y", 0))
        width = int(payload.get("width", image.width))
        height = int(payload.get("height", image.height))
        x = max(0, min(x, image.width - 1))
        y = max(0, min(y, image.height - 1))
        width = max(1, min(width, image.width - x))
        height = max(1, min(height, image.height - y))
        return PixelRoi(x=x, y=y, width=width, height=height)

    def _remember(self, roi: PixelRoi, score: float) -> None:
        self._last_roi = roi
        self._last_score = max(0.0, min(score, 1.0))


def _norm_to_pixel(region: tuple[float, float, float, float], width: int, height: int) -> PixelRoi:
    x = int(region[0] * width)
    y = int(region[1] * height)
    w = int(region[2] * width)
    h = int(region[3] * height)
    x = max(0, min(x, width - 1))
    y = max(0, min(y, height - 1))
    w = max(1, min(w, width - x))
    h = max(1, min(h, height - y))
    return PixelRoi(x=x, y=y, width=w, height=h)


def _score_ocr(result: OcrResult) -> float:
    text = " ".join(result.text.lower().split())
    if not text:
        return 0.0
    char_count = len(text.replace(" ", ""))
    length_score = min(1.0, char_count / 24.0)
    keyword_bonus = 0.0
    for keyword in TASK_KEYWORDS:
        if keyword in text:
            keyword_bonus = 0.2
            break
    base = 0.65 * max(0.0, min(1.0, result.confidence)) + 0.35 * length_score
    return min(1.0, base + keyword_bonus)


def _same_roi(left: PixelRoi, right: PixelRoi) -> bool:
    return (
        abs(left.x - right.x) <= 2
        and abs(left.y - right.y) <= 2
        and abs(left.width - right.width) <= 2
        and abs(left.height - right.height) <= 2
    )

