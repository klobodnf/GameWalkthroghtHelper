from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class Observation:
    game_id: str
    session_id: int
    timestamp: datetime
    task_text: str
    task_confidence: float
    cv_labels: list[str] = field(default_factory=list)
    frame_hash: str = ""
    roi: str | None = None


@dataclass(slots=True)
class GuideStepCandidate:
    state_id: str
    action_text: str
    text_keywords: list[str] = field(default_factory=list)
    cv_keywords: list[str] = field(default_factory=list)
    history_prior: float = 0.0
    priority: int = 0
    source_url: str = ""


@dataclass(slots=True)
class StateScore:
    candidate: GuideStepCandidate
    total: float
    text_match: float
    cv_match: float
    temporal: float
    history_prior: float


@dataclass(slots=True)
class ProgressDecision:
    definitive: bool
    primary: StateScore | None
    alternatives: list[StateScore]

    @property
    def speech_text(self) -> str:
        if self.primary is None:
            return "暂时无法确认下一步，建议继续观察任务提示。"
        if self.definitive:
            return f"下一步建议：{self.primary.candidate.action_text}"
        if not self.alternatives:
            return f"候选建议：{self.primary.candidate.action_text}"
        options = [self.primary.candidate.action_text]
        options.extend(item.candidate.action_text for item in self.alternatives[:1])
        joined = " 或 ".join(options)
        return f"当前不够确定，候选步骤：{joined}"

