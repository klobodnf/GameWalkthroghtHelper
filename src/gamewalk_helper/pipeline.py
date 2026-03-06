from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import sleep

from .capture.screen import ScreenCapture
from .config import AppConfig
from .db import Database
from .guides.fetcher import GuideFetcher
from .models import Observation, ProgressDecision
from .perception.cv import CvMatcher
from .perception.ocr import OcrEngine
from .perception.roi import TaskRoiLocator
from .progress import ProgressEngine
from .voice import VoiceCoach


@dataclass(slots=True)
class TickResult:
    decision: ProgressDecision
    observation: Observation | None


class GuideAssistantApp:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.db = Database(config.db_path)
        self.db.init_schema()
        self.capture = ScreenCapture()
        self.ocr = OcrEngine()
        self.roi_locator = TaskRoiLocator(
            auto_detect=config.roi_auto_detect,
            manual_roi=config.task_roi,
            min_score=config.roi_min_score,
            switch_margin=config.roi_switch_margin,
        )
        self.cv = CvMatcher(config.template_dir)
        self.fetcher = GuideFetcher(self.db, ttl_hours=config.query_ttl_hours)
        self.progress = ProgressEngine(
            strong_threshold=config.confidence_strong_threshold,
            margin_threshold=config.confidence_margin_threshold,
            max_suggestions=config.max_suggestions,
        )
        self.voice = VoiceCoach(self.db, cooldown_seconds=config.voice_cooldown_seconds)
        self.session_id: int | None = None

    def start_session(self, game_id: str) -> int:
        self.db.upsert_game(game_id=game_id)
        self.session_id = self.db.start_session(game_id)
        return self.session_id

    def stop_session(self) -> None:
        if self.session_id is None:
            return
        self.db.end_session(self.session_id)
        self.session_id = None

    def run_once(self, game_id: str) -> TickResult:
        if self.session_id is None:
            self.start_session(game_id)
        assert self.session_id is not None

        frame = self.capture.grab()
        if frame is None:
            return TickResult(
                decision=ProgressDecision(definitive=False, primary=None, alternatives=[]),
                observation=None,
            )

        roi_selection = self.roi_locator.locate(frame.image, self.ocr)
        ocr_result = roi_selection.ocr_result
        cv_labels = self.cv.match_labels(frame.image)
        observation = Observation(
            game_id=game_id,
            session_id=self.session_id,
            timestamp=datetime.now(timezone.utc),
            task_text=ocr_result.text,
            task_confidence=ocr_result.confidence,
            cv_labels=cv_labels,
            frame_hash=frame.hash_value,
            roi=roi_selection.roi.as_text(),
        )
        observation_id = self.db.add_observation(observation)
        previous_state = self.db.get_last_progress_state(self.session_id)
        candidates = self.fetcher.get_candidate_steps(game_id=game_id, task_text=observation.task_text)
        decision = self.progress.evaluate(
            observation=observation,
            candidates=candidates,
            previous_state_id=previous_state,
        )
        next_action = decision.speech_text
        state_id = decision.primary.candidate.state_id if decision.primary else None
        confidence = decision.primary.total if decision.primary else 0.0
        self.db.save_progress_state(
            session_id=self.session_id,
            state_id=state_id,
            confidence=confidence,
            evidence_observation_id=observation_id,
            next_action=next_action,
            definitive=decision.definitive,
        )
        if decision.primary is not None:
            self.voice.try_speak(game_id=game_id, text=next_action)
        return TickResult(decision=decision, observation=observation)

    def run_loop(self, game_id: str) -> None:
        try:
            while True:
                result = self.run_once(game_id)
                if result.observation is None:
                    print("未获取到屏幕帧，等待下一轮。")
                else:
                    text = result.observation.task_text or "<empty>"
                    print(f"[{result.observation.timestamp.isoformat()}] task={text}")
                sleep(self.config.loop_interval_seconds)
        except KeyboardInterrupt:
            print("停止监控。")
        finally:
            self.stop_session()
            self.db.close()
