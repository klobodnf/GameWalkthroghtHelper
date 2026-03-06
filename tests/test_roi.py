from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gamewalk_helper.perception.ocr import OcrResult
from gamewalk_helper.perception.roi import TaskRoiLocator


class FakeImage:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height

    def crop(self, box: tuple[int, int, int, int]) -> "FakeImage":
        x1, y1, x2, y2 = box
        return FakeImage(width=max(1, x2 - x1), height=max(1, y2 - y1))


class FakeOcrEngine:
    def __init__(self, results: list[OcrResult]) -> None:
        self.results = results
        self.call_index = 0

    def extract_task_text(self, _image: FakeImage) -> OcrResult:
        if self.call_index >= len(self.results):
            return OcrResult(text="", confidence=0.0)
        result = self.results[self.call_index]
        self.call_index += 1
        return result


class TaskRoiLocatorTests(unittest.TestCase):
    def test_selects_highest_scoring_region(self) -> None:
        locator = TaskRoiLocator(
            candidate_regions=[(0.0, 0.0, 0.5, 0.5), (0.5, 0.0, 0.5, 0.5)],
            switch_margin=0.05,
        )
        ocr = FakeOcrEngine(
            [
                OcrResult(text="背包", confidence=0.35),
                OcrResult(text="当前任务 前往村庄并与铁匠对话", confidence=0.62),
            ]
        )
        selection = locator.locate(FakeImage(1000, 1000), ocr)
        self.assertEqual(selection.roi.x, 500)
        self.assertGreater(selection.score, 0.6)

    def test_keeps_previous_roi_when_margin_is_small(self) -> None:
        locator = TaskRoiLocator(
            candidate_regions=[(0.0, 0.0, 0.5, 0.5), (0.5, 0.0, 0.5, 0.5)],
            switch_margin=0.12,
        )
        ocr = FakeOcrEngine(
            [
                OcrResult(text="当前任务 前往城门", confidence=0.70),
                OcrResult(text="当前任务 前往城门", confidence=0.55),
                OcrResult(text="当前任务 前往城门", confidence=0.64),
                OcrResult(text="当前任务 前往城门", confidence=0.67),
            ]
        )
        first = locator.locate(FakeImage(1000, 1000), ocr)
        second = locator.locate(FakeImage(1000, 1000), ocr)
        self.assertEqual(first.roi.x, 0)
        self.assertEqual(second.roi.x, 0)

    def test_falls_back_to_full_frame_when_all_candidates_are_weak(self) -> None:
        locator = TaskRoiLocator(
            candidate_regions=[(0.0, 0.0, 0.5, 0.5), (0.5, 0.0, 0.5, 0.5)],
            min_score=0.3,
        )
        ocr = FakeOcrEngine(
            [
                OcrResult(text="", confidence=0.0),
                OcrResult(text="", confidence=0.0),
                OcrResult(text="", confidence=0.0),
            ]
        )
        selection = locator.locate(FakeImage(1000, 1000), ocr)
        self.assertEqual(selection.roi.x, 0)
        self.assertEqual(selection.roi.y, 0)
        self.assertEqual(selection.roi.width, 1000)
        self.assertEqual(selection.roi.height, 1000)


if __name__ == "__main__":
    unittest.main()

