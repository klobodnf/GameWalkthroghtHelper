from __future__ import annotations

from collections.abc import Callable

from .runtime_control import RuntimeControl


StatusHandler = Callable[[str], None]


class HotkeyManager:
    def __init__(
        self,
        control: RuntimeControl,
        enabled: bool = True,
        status_handler: StatusHandler | None = None,
    ) -> None:
        self.control = control
        self.enabled = enabled
        self.status_handler = status_handler or (lambda text: print(text))
        self._listener = None
        self._is_active = False

    def start(self) -> bool:
        if not self.enabled:
            return False
        try:
            from pynput import keyboard  # type: ignore
        except Exception:
            self.status_handler("热键未启用：缺少 pynput 依赖。")
            return False

        bindings = {
            "<ctrl>+<alt>+m": self._handle_mute,
            "<ctrl>+<alt>+p": self._handle_pause,
            "<ctrl>+<alt>+h": self._handle_force_hint,
            "<ctrl>+<alt>+d": self._handle_detail,
            "<ctrl>+<alt>+q": self._handle_quit,
        }
        self._listener = keyboard.GlobalHotKeys(bindings)
        self._listener.start()
        self._is_active = True
        self.status_handler(
            "热键已启用: Ctrl+Alt+M 静音, Ctrl+Alt+P 暂停, Ctrl+Alt+H 强制提示, Ctrl+Alt+D 详情级别, Ctrl+Alt+Q 退出。"
        )
        return True

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
        self._listener = None
        self._is_active = False

    @property
    def is_active(self) -> bool:
        return self._is_active

    def _handle_mute(self) -> None:
        muted = self.control.toggle_mute()
        self.status_handler("语音已静音。" if muted else "语音已恢复。")

    def _handle_pause(self) -> None:
        paused = self.control.toggle_pause()
        self.status_handler("识别已暂停。" if paused else "识别已继续。")

    def _handle_force_hint(self) -> None:
        self.control.request_force_hint()
        self.status_handler("已请求立即刷新提示。")

    def _handle_detail(self) -> None:
        level = self.control.cycle_detail()
        self.status_handler(f"提示详细级别已切换到 L{level}。")

    def _handle_quit(self) -> None:
        self.control.stop()
        self.status_handler("收到退出指令，正在停止。")

