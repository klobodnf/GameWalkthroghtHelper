from __future__ import annotations

from collections.abc import Callable
from threading import Event, Thread
from time import sleep
import re

from .runtime_control import RuntimeControl


StatusHandler = Callable[[str], None]


def parse_voice_command(text: str, wake_word: str = "") -> str | None:
    normalized = _normalize_text(text)
    if not normalized:
        return None

    wake = _normalize_text(wake_word)
    if wake and wake not in normalized:
        return None
    if wake:
        normalized = normalized.replace(wake, "")

    if _contains_any(normalized, ["取消静音", "恢复语音", "unmute", "voiceon"]):
        return "unmute"
    if _contains_any(normalized, ["静音", "闭嘴", "mute", "silence"]):
        return "mute"
    if _contains_any(normalized, ["继续识别", "继续", "恢复识别", "resume", "continue"]):
        return "resume"
    if _contains_any(normalized, ["暂停识别", "暂停", "pause", "holdon"]):
        return "pause"
    if _contains_any(normalized, ["刷新提示", "下一步", "提示", "hint", "nextstep", "refreshhint"]):
        return "force_hint"
    if _contains_any(normalized, ["详细", "细节", "detail"]):
        return "detail"
    if _contains_any(normalized, ["退出助手", "关闭助手", "停止程序", "quit", "exit", "closehelper"]):
        return "quit"
    return None


class VoiceCommandManager:
    def __init__(
        self,
        control: RuntimeControl,
        enabled: bool = False,
        status_handler: StatusHandler | None = None,
        language: str = "zh-CN",
        wake_word: str = "",
        listen_timeout_seconds: float = 1.5,
        phrase_time_limit_seconds: float = 3.0,
        error_backoff_seconds: float = 3.0,
    ) -> None:
        self.control = control
        self.enabled = enabled
        self.status_handler = status_handler or (lambda text: print(text))
        self.language = language
        self.wake_word = wake_word
        self.listen_timeout_seconds = max(0.8, float(listen_timeout_seconds))
        self.phrase_time_limit_seconds = max(1.0, float(phrase_time_limit_seconds))
        self.error_backoff_seconds = max(1.0, float(error_backoff_seconds))

        self._stop_event = Event()
        self._worker: Thread | None = None
        self._is_active = False
        self._recognizer = None
        self._microphone = None

    def start(self) -> bool:
        if not self.enabled:
            return False
        try:
            import speech_recognition as sr  # type: ignore
        except Exception:
            self.status_handler("语音输入未启用：缺少 SpeechRecognition 依赖。")
            return False

        try:
            self._recognizer = sr.Recognizer()
            self._microphone = sr.Microphone()
            with self._microphone as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.4)
        except Exception:
            self.status_handler("语音输入未启用：未找到可用麦克风或初始化失败。")
            self._recognizer = None
            self._microphone = None
            return False

        self._stop_event.clear()
        self._worker = Thread(target=self._run_loop, name="gwh-voice-input", daemon=True)
        self._worker.start()
        self._is_active = True
        if self.wake_word.strip():
            self.status_handler(f"语音输入已启用（唤醒词：{self.wake_word.strip()}）。")
        else:
            self.status_handler("语音输入已启用。")
        return True

    def stop(self) -> None:
        self._stop_event.set()
        worker = self._worker
        if worker is not None and worker.is_alive():
            worker.join(timeout=2.0)
        self._worker = None
        self._is_active = False

    @property
    def is_active(self) -> bool:
        return self._is_active

    def _run_loop(self) -> None:
        assert self._recognizer is not None
        assert self._microphone is not None
        recognizer = self._recognizer
        microphone = self._microphone

        try:
            import speech_recognition as sr  # type: ignore
        except Exception:
            self._is_active = False
            return

        while not self._stop_event.is_set():
            try:
                with microphone as source:
                    audio = recognizer.listen(
                        source,
                        timeout=self.listen_timeout_seconds,
                        phrase_time_limit=self.phrase_time_limit_seconds,
                    )
            except sr.WaitTimeoutError:
                continue
            except Exception:
                sleep(self.error_backoff_seconds)
                continue

            try:
                transcript = recognizer.recognize_google(audio, language=self.language)
            except sr.UnknownValueError:
                continue
            except sr.RequestError:
                sleep(self.error_backoff_seconds)
                continue
            except Exception:
                sleep(self.error_backoff_seconds)
                continue

            self._apply_transcript(transcript)

        self._is_active = False

    def _apply_transcript(self, transcript: str) -> None:
        command = parse_voice_command(text=transcript, wake_word=self.wake_word)
        if command is None:
            return

        if command == "mute":
            if not self.control.snapshot().muted:
                self.control.toggle_mute()
            self.status_handler("语音命令：已静音。")
            return

        if command == "unmute":
            if self.control.snapshot().muted:
                self.control.toggle_mute()
            self.status_handler("语音命令：已取消静音。")
            return

        if command == "pause":
            if not self.control.snapshot().paused:
                self.control.toggle_pause()
            self.status_handler("语音命令：已暂停识别。")
            return

        if command == "resume":
            if self.control.snapshot().paused:
                self.control.toggle_pause()
            self.status_handler("语音命令：已继续识别。")
            return

        if command == "force_hint":
            self.control.request_force_hint()
            self.status_handler("语音命令：已刷新提示。")
            return

        if command == "detail":
            level = self.control.cycle_detail()
            self.status_handler(f"语音命令：详细级别切换到 L{level}。")
            return

        if command == "quit":
            self.control.stop()
            self.status_handler("语音命令：已停止助手。")


def _normalize_text(text: str) -> str:
    lowered = text.strip().lower()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", lowered)


def _contains_any(text: str, keywords: list[str]) -> bool:
    for keyword in keywords:
        if _normalize_text(keyword) in text:
            return True
    return False
