from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from queue import Empty, Queue
from threading import Event, Thread

_STOP_SIGNAL = object()


@dataclass(slots=True)
class OverlayStatus:
    game_id: str
    task_text: str
    hint_text: str
    confidence: float
    definitive: bool
    muted: bool
    paused: bool
    detail_level: int
    updated_at: datetime


class OverlayWindow:
    def __init__(
        self,
        enabled: bool = True,
        title: str = "GameWalk Guide",
        width: int = 560,
        height: int = 220,
        pos_x: int = 24,
        pos_y: int = 24,
    ) -> None:
        self.enabled = enabled
        self.title = title
        self.width = width
        self.height = height
        self.pos_x = pos_x
        self.pos_y = pos_y
        self._queue: Queue[object] = Queue()
        self._thread: Thread | None = None
        self._started = False
        self._stop = Event()

    def start(self) -> bool:
        if not self.enabled:
            return False
        if self._started:
            return True
        try:
            import tkinter  # noqa: F401
        except Exception:
            print("悬浮窗未启用：缺少 tkinter 支持。")
            return False
        self._thread = Thread(target=self._run, name="gwh-overlay", daemon=True)
        self._thread.start()
        self._started = True
        return True

    def stop(self) -> None:
        if not self._started:
            return
        self._stop.set()
        self._queue.put(_STOP_SIGNAL)
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2.0)
        self._thread = None
        self._started = False

    def update(self, status: OverlayStatus) -> None:
        if not self._started:
            return
        self._queue.put(status)

    def _run(self) -> None:
        import tkinter as tk

        root = tk.Tk()
        root.title(self.title)
        root.geometry(f"{self.width}x{self.height}+{self.pos_x}+{self.pos_y}")
        root.attributes("-topmost", True)
        root.resizable(False, False)
        root.configure(bg="#111318")

        title_label = tk.Label(
            root,
            text="GameWalk Guide",
            fg="#f8f8f2",
            bg="#111318",
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        )
        title_label.pack(fill="x", padx=12, pady=(10, 2))

        state_label = tk.Label(
            root,
            text="状态: 初始化中",
            fg="#a7f3d0",
            bg="#111318",
            font=("Segoe UI", 10),
            anchor="w",
        )
        state_label.pack(fill="x", padx=12)

        task_label = tk.Label(
            root,
            text="任务: -",
            fg="#dbeafe",
            bg="#111318",
            wraplength=self.width - 24,
            justify="left",
            font=("Segoe UI", 10),
            anchor="w",
        )
        task_label.pack(fill="x", padx=12, pady=(6, 0))

        hint_label = tk.Label(
            root,
            text="建议: -",
            fg="#fef9c3",
            bg="#111318",
            wraplength=self.width - 24,
            justify="left",
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        )
        hint_label.pack(fill="x", padx=12, pady=(6, 0))

        bottom_label = tk.Label(
            root,
            text="快捷键: Ctrl+Alt+M/P/H/D/Q",
            fg="#9ca3af",
            bg="#111318",
            font=("Segoe UI", 9),
            anchor="w",
        )
        bottom_label.pack(fill="x", padx=12, pady=(8, 8))

        def poll_queue() -> None:
            if self._stop.is_set():
                root.destroy()
                return

            latest: object | None = None
            while True:
                try:
                    item = self._queue.get_nowait()
                except Empty:
                    break
                latest = item

            if latest is _STOP_SIGNAL:
                root.destroy()
                return

            if latest is None:
                root.after(120, poll_queue)
                return

            status = latest
            if not isinstance(status, OverlayStatus):
                root.after(120, poll_queue)
                return

            state_parts = [
                f"游戏: {status.game_id}",
                "暂停中" if status.paused else "运行中",
                "静音" if status.muted else "有声",
                f"L{status.detail_level}",
            ]
            confidence_text = f"{status.confidence * 100:.0f}%"
            state_parts.append("明确" if status.definitive else "候选")
            state_parts.append(f"置信度 {confidence_text}")
            state_label.config(text="状态: " + " | ".join(state_parts))

            task_text = status.task_text.strip() or "未识别到任务文本"
            hint_text = status.hint_text.strip() or "暂无提示"
            task_label.config(text=f"任务: {task_text}")
            hint_label.config(text=f"建议: {hint_text}")
            bottom_label.config(
                text=f"快捷键 Ctrl+Alt+M/P/H/D/Q | 更新时间 {status.updated_at.strftime('%H:%M:%S')}"
            )
            root.after(120, poll_queue)

        root.after(120, poll_queue)
        try:
            root.mainloop()
        except Exception:
            pass
