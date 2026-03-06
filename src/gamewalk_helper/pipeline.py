from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import sleep

from .capture.screen import ScreenCapture
from .config import AppConfig
from .db import Database
from .guides.fetcher import GuideFetcher, parse_source_domains
from .hotkeys import HotkeyManager
from .models import GuideStepCandidate, Observation, ProgressDecision, StateScore
from .perception.cv import CvMatcher
from .perception.ocr import OcrEngine
from .perception.roi import TaskRoiLocator
from .progress import ProgressEngine
from .runtime_control import ControlSnapshot, RuntimeControl
from .scene import SceneMatch, SceneProgressMatcher
from .ui.overlay import OverlayStatus, OverlayWindow
from .voice import VoiceCoach


@dataclass(slots=True)
class TickResult:
    decision: ProgressDecision
    observation: Observation | None
    hint_text: str = ""
    spoken: bool = False


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
        self.fetcher = GuideFetcher(
            self.db,
            ttl_hours=config.query_ttl_hours,
            preferred_domains=parse_source_domains(config.guide_source_domains),
            per_source_limit=config.guide_per_source_limit,
            max_candidates=config.guide_max_candidates,
        )
        self.progress = ProgressEngine(
            strong_threshold=config.confidence_strong_threshold,
            margin_threshold=config.confidence_margin_threshold,
            max_suggestions=config.max_suggestions,
        )
        self.scene_matcher = SceneProgressMatcher(
            db=self.db,
            hash_size=config.scene_hash_size,
            default_distance_threshold=config.scene_match_distance_threshold,
        )
        self.voice = VoiceCoach(
            self.db,
            cooldown_seconds=config.voice_cooldown_seconds,
            voice_volume=config.voice_volume,
        )
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

    def run_once(
        self,
        game_id: str,
        *,
        speak: bool = True,
        force_voice: bool = False,
        detail_level: int = 1,
    ) -> TickResult:
        if self.session_id is None:
            self.start_session(game_id)
        assert self.session_id is not None

        frame = self.capture.grab()
        if frame is None:
            return TickResult(
                decision=ProgressDecision(definitive=False, primary=None, alternatives=[]),
                observation=None,
                hint_text="未获取到屏幕帧。",
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
        task_text = observation.task_text.strip()

        scene_match = self._maybe_match_scene(game_id=game_id, task_text=task_text, image=frame.image)
        candidates = self.fetcher.get_candidate_steps(game_id=game_id, task_text=task_text) if task_text else []
        if scene_match is not None:
            candidates.insert(0, _scene_candidate(scene_match))

        if scene_match is not None and not task_text:
            decision = self._build_scene_decision(scene_match=scene_match, previous_state=previous_state)
        else:
            decision = self.progress.evaluate(
                observation=observation,
                candidates=candidates,
                previous_state_id=previous_state,
            )
        next_action = _format_hint_text(decision, detail_level=detail_level)
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
        should_voice = speak and (decision.primary is not None or force_voice)
        spoken = False
        if should_voice:
            spoken = self.voice.try_speak(
                game_id=game_id,
                text=next_action,
                ignore_cooldown=force_voice,
            )
        return TickResult(decision=decision, observation=observation, hint_text=next_action, spoken=spoken)

    def run_loop(
        self,
        game_id: str,
        control: RuntimeControl | None = None,
        overlay: OverlayWindow | None = None,
        hotkeys: HotkeyManager | None = None,
    ) -> None:
        runtime_control = control or RuntimeControl()
        overlay_enabled = overlay.start() if overlay is not None else False
        hotkeys_enabled = hotkeys.start() if hotkeys is not None else False
        if hotkeys_enabled:
            print("全局热键已启用。")
        if overlay_enabled:
            print("悬浮窗已启用。")

        last_hint = "等待识别任务文本..."
        last_task = ""

        try:
            while not runtime_control.should_stop():
                force_hint = runtime_control.consume_force_hint()
                snapshot = runtime_control.snapshot()

                if snapshot.paused and not force_hint:
                    self._publish_overlay(
                        overlay=overlay,
                        game_id=game_id,
                        task_text=last_task,
                        hint_text=last_hint,
                        confidence=0.0,
                        definitive=False,
                        snapshot=snapshot,
                    )
                    sleep(self.config.loop_interval_seconds)
                    continue

                result = self.run_once(
                    game_id,
                    speak=not snapshot.muted,
                    force_voice=force_hint,
                    detail_level=snapshot.detail_level,
                )
                if result.observation is None:
                    print("未获取到屏幕帧，等待下一轮。")
                    self._publish_overlay(
                        overlay=overlay,
                        game_id=game_id,
                        task_text=last_task,
                        hint_text=result.hint_text or last_hint,
                        confidence=0.0,
                        definitive=False,
                        snapshot=snapshot,
                    )
                else:
                    last_task = result.observation.task_text
                    last_hint = result.hint_text
                    text = result.observation.task_text or "<empty>"
                    confidence = 0.0
                    definitive = False
                    if result.decision.primary is not None:
                        confidence = result.decision.primary.total
                        definitive = result.decision.definitive
                    self._publish_overlay(
                        overlay=overlay,
                        game_id=game_id,
                        task_text=text,
                        hint_text=result.hint_text,
                        confidence=confidence,
                        definitive=definitive,
                        snapshot=snapshot,
                    )
                    print(f"[{result.observation.timestamp.isoformat()}] task={text}")
                sleep(self.config.loop_interval_seconds)
        except KeyboardInterrupt:
            print("停止监控。")
        finally:
            if hotkeys is not None:
                hotkeys.stop()
            if overlay is not None:
                overlay.stop()
            self.stop_session()
            self.db.close()

    def _publish_overlay(
        self,
        overlay: OverlayWindow | None,
        game_id: str,
        task_text: str,
        hint_text: str,
        confidence: float,
        definitive: bool,
        snapshot: ControlSnapshot,
    ) -> None:
        if overlay is None:
            return
        overlay.update(
            OverlayStatus(
                game_id=game_id,
                task_text=task_text,
                hint_text=hint_text,
                confidence=max(0.0, min(confidence, 1.0)),
                definitive=definitive,
                muted=snapshot.muted,
                paused=snapshot.paused,
                detail_level=snapshot.detail_level,
                updated_at=datetime.now(timezone.utc),
            )
        )

    def _maybe_match_scene(self, game_id: str, task_text: str, image) -> SceneMatch | None:
        if not self.config.scene_match_enabled:
            return None
        if self.config.scene_match_when_no_task and task_text:
            return None
        return self.scene_matcher.match(game_id=game_id, image=image)

    def _build_scene_decision(self, scene_match: SceneMatch, previous_state: str | None) -> ProgressDecision:
        candidate = _scene_candidate(scene_match)
        temporal = 1.0 if previous_state == candidate.state_id else 0.5
        total = min(0.95, scene_match.confidence * 0.85 + temporal * 0.15)
        definitive = total >= self.config.scene_confidence_threshold
        return ProgressDecision(
            definitive=definitive,
            primary=StateScore(
                candidate=candidate,
                total=round(total, 4),
                text_match=0.0,
                cv_match=0.0,
                temporal=temporal,
                history_prior=scene_match.confidence,
            ),
            alternatives=[],
        )


def _format_hint_text(decision: ProgressDecision, detail_level: int) -> str:
    if decision.primary is None:
        return "暂时无法确认下一步，建议继续观察任务提示。"

    action = decision.primary.candidate.action_text.strip()
    if detail_level <= 0:
        return action

    if decision.definitive:
        if detail_level == 1:
            return f"下一步：{action}"
        detail_suffix = ""
        source = decision.primary.candidate.source_url.strip()
        if source:
            detail_suffix = f" 参考: {source}"
        return f"下一步建议：{action}{detail_suffix}"

    options = [action]
    options.extend(item.candidate.action_text.strip() for item in decision.alternatives[:1] if item.candidate.action_text.strip())
    joined = " 或 ".join(options)
    if detail_level == 1:
        return f"候选步骤：{joined}"
    return f"当前不够确定，候选步骤：{joined}。建议按任务面板再确认一次。"


def _scene_candidate(scene_match: SceneMatch) -> GuideStepCandidate:
    return GuideStepCandidate(
        state_id=scene_match.state_id,
        action_text=scene_match.hint_text,
        text_keywords=[],
        cv_keywords=[],
        history_prior=scene_match.confidence,
        priority=85,
        source_url=f"scene://{scene_match.label}",
    )
