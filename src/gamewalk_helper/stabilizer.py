from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass(slots=True)
class StableProgress:
    state_id: str | None
    hint_text: str
    confidence: float
    stable: bool
    hits: int


@dataclass(slots=True)
class _Signal:
    state_id: str | None
    hint_text: str
    confidence: float


class ProgressStabilizer:
    def __init__(self, window_size: int = 5, stable_hits: int = 3) -> None:
        self.window_size = max(3, int(window_size))
        self.stable_hits = max(2, int(stable_hits))
        self._signals: deque[_Signal] = deque(maxlen=self.window_size)

    def update(self, state_id: str | None, hint_text: str, confidence: float) -> StableProgress:
        signal = _Signal(state_id=state_id, hint_text=hint_text, confidence=max(0.0, min(1.0, confidence)))
        self._signals.append(signal)
        return self._build_result()

    def _build_result(self) -> StableProgress:
        stats: dict[str, dict[str, float | str | int]] = {}
        for item in self._signals:
            if not item.state_id:
                continue
            record = stats.setdefault(
                item.state_id,
                {"hits": 0, "confidence_sum": 0.0, "latest_hint": item.hint_text, "latest_order": -1},
            )
            record["hits"] = int(record["hits"]) + 1
            record["confidence_sum"] = float(record["confidence_sum"]) + item.confidence
            record["latest_hint"] = item.hint_text

        if not stats:
            return StableProgress(state_id=None, hint_text="", confidence=0.0, stable=False, hits=0)

        best_state = None
        best_hits = -1
        best_avg = -1.0
        best_hint = ""
        for state, record in stats.items():
            hits = int(record["hits"])
            avg = float(record["confidence_sum"]) / max(1, hits)
            if hits > best_hits or (hits == best_hits and avg > best_avg):
                best_state = state
                best_hits = hits
                best_avg = avg
                best_hint = str(record["latest_hint"])

        stable = best_hits >= self.stable_hits
        return StableProgress(
            state_id=best_state,
            hint_text=best_hint,
            confidence=max(0.0, min(1.0, best_avg)),
            stable=stable,
            hits=best_hits,
        )

