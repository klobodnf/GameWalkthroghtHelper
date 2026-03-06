from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class OcrResult:
    text: str
    confidence: float


class OcrEngine:
    def __init__(self, language: str = "ch", use_angle_cls: bool = True) -> None:
        self.language = language
        self.use_angle_cls = use_angle_cls
        self._backend = None
        self._init_backend()

    def _init_backend(self) -> None:
        try:
            from paddleocr import PaddleOCR  # type: ignore

            self._backend = ("paddle", PaddleOCR(use_angle_cls=self.use_angle_cls, lang=self.language))
            return
        except Exception:
            pass
        try:
            import pytesseract  # type: ignore

            self._backend = ("tesseract", pytesseract)
        except Exception:
            self._backend = None

    def extract_task_text(self, image: Any) -> OcrResult:
        if self._backend is None:
            return OcrResult(text="", confidence=0.0)
        name, backend = self._backend
        if name == "paddle":
            return _run_paddle(backend, image)
        return _run_tesseract(backend, image)


def _run_paddle(backend: Any, image: Any) -> OcrResult:
    try:
        import numpy as np  # type: ignore
    except Exception:
        return OcrResult(text="", confidence=0.0)
    try:
        result = backend.ocr(np.array(image), cls=True)
        if not result or not result[0]:
            return OcrResult(text="", confidence=0.0)
        texts: list[str] = []
        confidences: list[float] = []
        for line in result[0]:
            text = line[1][0].strip()
            conf = float(line[1][1])
            if text:
                texts.append(text)
                confidences.append(conf)
        if not texts:
            return OcrResult(text="", confidence=0.0)
        avg_conf = sum(confidences) / len(confidences)
        return OcrResult(text=" ".join(texts), confidence=round(avg_conf, 4))
    except Exception:
        return OcrResult(text="", confidence=0.0)


def _run_tesseract(backend: Any, image: Any) -> OcrResult:
    try:
        text = backend.image_to_string(image)
    except Exception:
        return OcrResult(text="", confidence=0.0)
    clean = " ".join(text.split())
    return OcrResult(text=clean, confidence=0.5 if clean else 0.0)

