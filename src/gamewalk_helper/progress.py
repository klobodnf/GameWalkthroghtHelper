from __future__ import annotations

from dataclasses import dataclass

from .models import GuideStepCandidate, Observation, ProgressDecision, StateScore


@dataclass(slots=True)
class ProgressWeights:
    text: float = 0.45
    cv: float = 0.25
    temporal: float = 0.15
    history: float = 0.15


class ProgressEngine:
    def __init__(
        self,
        strong_threshold: float = 0.65,
        margin_threshold: float = 0.15,
        max_suggestions: int = 2,
        weights: ProgressWeights | None = None,
    ) -> None:
        self.strong_threshold = strong_threshold
        self.margin_threshold = margin_threshold
        self.max_suggestions = max_suggestions
        self.weights = weights or ProgressWeights()

    def evaluate(
        self,
        observation: Observation,
        candidates: list[GuideStepCandidate],
        previous_state_id: str | None,
    ) -> ProgressDecision:
        if not candidates:
            return ProgressDecision(definitive=False, primary=None, alternatives=[])

        scores: list[StateScore] = []
        for candidate in candidates:
            text_score = _text_match(observation.task_text, candidate.text_keywords)
            cv_score = _cv_match(observation.cv_labels, candidate.cv_keywords)
            temporal_score = _temporal_score(candidate.state_id, previous_state_id)
            history_score = max(0.0, min(1.0, candidate.history_prior))
            total = (
                self.weights.text * text_score
                + self.weights.cv * cv_score
                + self.weights.temporal * temporal_score
                + self.weights.history * history_score
            )
            total += min(0.1, candidate.priority * 0.01)
            scores.append(
                StateScore(
                    candidate=candidate,
                    total=round(total, 4),
                    text_match=text_score,
                    cv_match=cv_score,
                    temporal=temporal_score,
                    history_prior=history_score,
                )
            )

        scores.sort(key=lambda item: item.total, reverse=True)
        top = scores[0]
        second = scores[1] if len(scores) > 1 else None
        margin = top.total - (second.total if second else 0.0)
        definitive = top.total >= self.strong_threshold and margin >= self.margin_threshold
        alternatives = scores[1 : self.max_suggestions] if not definitive else []
        return ProgressDecision(definitive=definitive, primary=top, alternatives=alternatives)


def _text_match(task_text: str, keywords: list[str]) -> float:
    clean_text = task_text.strip().lower()
    if not clean_text or not keywords:
        return 0.0
    hits = 0.0
    for keyword in keywords:
        word = keyword.strip().lower()
        if not word:
            continue
        if word in clean_text:
            hits += 1.0
            continue
        overlap = _longest_overlap_ratio(clean_text, word)
        hits += overlap
    raw = hits / max(1, len(keywords))
    return min(1.0, raw)


def _cv_match(labels: list[str], keywords: list[str]) -> float:
    if not labels or not keywords:
        return 0.0
    lower_labels = {item.strip().lower() for item in labels if item.strip()}
    lower_keywords = {item.strip().lower() for item in keywords if item.strip()}
    if not lower_keywords:
        return 0.0
    matched = len(lower_labels.intersection(lower_keywords))
    return matched / len(lower_keywords)


def _temporal_score(state_id: str, previous_state_id: str | None) -> float:
    if previous_state_id is None:
        return 0.4
    if state_id == previous_state_id:
        return 1.0
    return 0.2


def _longest_overlap_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    best = 0
    for index in range(len(b)):
        for end in range(index + 1, len(b) + 1):
            piece = b[index:end]
            if piece in a:
                best = max(best, len(piece))
    return best / len(b)

