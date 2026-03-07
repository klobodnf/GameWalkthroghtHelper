from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from tkinter import BOTH, END, HORIZONTAL, LEFT, RIGHT, DoubleVar, StringVar, Tk, W, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import traceback

from .config import load_config
from .db import Database
from .hotkeys import HotkeyManager
from .pipeline import GuideAssistantApp
from .runtime_control import RuntimeControl
from .scene import SceneKeyframeManager
from .steam import SteamGame, scan_installed_games
from .ui.overlay import OverlayWindow
from .voice import clamp_volume


@dataclass(slots=True)
class GuiRunOptions:
    game_id: str
    run_mode: str
    overlay_enabled: bool
    hotkeys_enabled: bool
    ai_advisor_enabled: bool
    voice_volume: float


def game_display_name(game: SteamGame) -> str:
    return f"{game.name} (steam_{game.app_id})"


def resolve_game_id(display_name: str, lookup: dict[str, str], manual_game_id: str) -> str | None:
    manual = manual_game_id.strip()
    if manual:
        return manual
    chosen = display_name.strip()
    if not chosen:
        return None
    return lookup.get(chosen)


class GuideDesktopApp:
    def __init__(self, config_path: str) -> None:
        self.config_path = config_path
        self.base_config = load_config(config_path)
        self.root = Tk()
        self.root.title("GameWalkthroghtHelper")
        self.root.geometry("920x680")
        self.root.minsize(860, 620)

        self._queue: Queue[tuple[str, str]] = Queue()
        self._games: list[SteamGame] = []
        self._display_to_id: dict[str, str] = {}
        self._worker: Thread | None = None
        self._runtime_control: RuntimeControl | None = None
        self._active_app: GuideAssistantApp | None = None

        self.selected_game_var = StringVar(value="")
        self.manual_game_id_var = StringVar(value="")
        self.scene_label_var = StringVar(value="")
        self.scene_action_var = StringVar(value="")
        self.mode_var = StringVar(value="loop")
        self.overlay_var = StringVar(value="1" if self.base_config.overlay_enabled else "0")
        self.hotkeys_var = StringVar(value="1" if self.base_config.hotkeys_enabled else "0")
        self.ai_advisor_var = StringVar(value="1" if self.base_config.ai_advisor_enabled else "0")
        initial_volume = clamp_volume(self.base_config.voice_volume)
        self.voice_volume_var = DoubleVar(value=round(initial_volume * 100, 0))
        self.voice_volume_label_var = StringVar(value=self._format_volume_percent(initial_volume))
        self.status_var = StringVar(value="Ready")

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(120, self._drain_queue)
        self.refresh_steam_games()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill=BOTH, expand=True)

        header = ttk.Label(
            frame,
            text="GameWalkthroghtHelper - Desktop Control",
            font=("Segoe UI", 14, "bold"),
        )
        header.pack(anchor=W, pady=(0, 10))

        steam_bar = ttk.Frame(frame)
        steam_bar.pack(fill="x", pady=(0, 8))
        ttk.Button(steam_bar, text="Refresh Steam Library", command=self.refresh_steam_games).pack(side=LEFT)
        ttk.Button(steam_bar, text="List Scene Keyframes", command=self.list_scene_keyframes).pack(side=LEFT, padx=(8, 0))
        ttk.Label(steam_bar, textvariable=self.status_var, foreground="#0066aa").pack(side=LEFT, padx=(12, 0))

        picker = ttk.Frame(frame)
        picker.pack(fill="x", pady=(0, 10))
        ttk.Label(picker, text="Installed Steam Games").grid(row=0, column=0, sticky=W)
        self.game_combo = ttk.Combobox(
            picker,
            textvariable=self.selected_game_var,
            state="readonly",
            width=70,
        )
        self.game_combo.grid(row=1, column=0, sticky="we", padx=(0, 8))
        picker.grid_columnconfigure(0, weight=1)

        manual = ttk.Frame(frame)
        manual.pack(fill="x", pady=(0, 12))
        ttk.Label(manual, text="Manual game_id (optional, overrides selection)").pack(anchor=W)
        ttk.Entry(manual, textvariable=self.manual_game_id_var).pack(fill="x")

        scene_frame = ttk.LabelFrame(frame, text="No-task Scene Keyframe Capture", padding=10)
        scene_frame.pack(fill="x", pady=(0, 10))
        scene_row = ttk.Frame(scene_frame)
        scene_row.pack(fill="x")
        ttk.Label(scene_row, text="Label").pack(side=LEFT)
        ttk.Entry(scene_row, textvariable=self.scene_label_var, width=28).pack(side=LEFT, padx=(8, 12))
        ttk.Label(scene_row, text="Action Hint").pack(side=LEFT)
        ttk.Entry(scene_row, textvariable=self.scene_action_var, width=42).pack(side=LEFT, padx=(8, 12))
        ttk.Button(scene_row, text="Capture Current Screen", command=self.capture_scene_keyframe).pack(side=LEFT)

        options = ttk.LabelFrame(frame, text="Run Options", padding=10)
        options.pack(fill="x", pady=(0, 10))

        mode_bar = ttk.Frame(options)
        mode_bar.pack(fill="x", pady=(0, 8))
        ttk.Label(mode_bar, text="Mode:").pack(side=LEFT)
        ttk.Radiobutton(mode_bar, text="Loop (real-time)", value="loop", variable=self.mode_var).pack(side=LEFT, padx=(10, 0))
        ttk.Radiobutton(mode_bar, text="Once (single tick)", value="once", variable=self.mode_var).pack(side=LEFT, padx=(10, 0))

        toggle_bar = ttk.Frame(options)
        toggle_bar.pack(fill="x")
        ttk.Checkbutton(toggle_bar, text="Enable Overlay", variable=self.overlay_var, onvalue="1", offvalue="0").pack(side=LEFT)
        ttk.Checkbutton(toggle_bar, text="Enable Global Hotkeys", variable=self.hotkeys_var, onvalue="1", offvalue="0").pack(side=LEFT, padx=(10, 0))
        ttk.Checkbutton(toggle_bar, text="Enable AI Advisor", variable=self.ai_advisor_var, onvalue="1", offvalue="0").pack(side=LEFT, padx=(10, 0))

        voice_bar = ttk.Frame(options)
        voice_bar.pack(fill="x", pady=(8, 0))
        ttk.Label(voice_bar, text="Voice Volume").pack(side=LEFT)
        self.voice_scale = ttk.Scale(
            voice_bar,
            from_=0,
            to=100,
            orient=HORIZONTAL,
            variable=self.voice_volume_var,
            command=self._on_volume_change,
            length=260,
        )
        self.voice_scale.pack(side=LEFT, padx=(10, 8))
        ttk.Label(voice_bar, textvariable=self.voice_volume_label_var, width=6).pack(side=LEFT)
        self.apply_volume_btn = ttk.Button(voice_bar, text="Apply", command=self.apply_voice_volume)
        self.apply_volume_btn.pack(side=LEFT, padx=(8, 0))

        action_bar = ttk.Frame(frame)
        action_bar.pack(fill="x", pady=(0, 10))
        self.start_btn = ttk.Button(action_bar, text="Start", command=self.start_run)
        self.start_btn.pack(side=LEFT)
        self.stop_btn = ttk.Button(action_bar, text="Stop", command=self.stop_run, state="disabled")
        self.stop_btn.pack(side=LEFT, padx=(8, 0))
        ttk.Button(action_bar, text="Quit", command=self._on_close).pack(side=RIGHT)

        self.log_box = ScrolledText(frame, height=20, font=("Consolas", 10))
        self.log_box.pack(fill=BOTH, expand=True)
        self.log_box.configure(state="disabled")

    def start(self) -> None:
        self.root.mainloop()

    def refresh_steam_games(self) -> None:
        self.status_var.set("Scanning Steam library...")
        self._enqueue_log("Scanning Steam library...")
        root, games = scan_installed_games()
        self._games = games
        self._display_to_id.clear()

        values: list[str] = []
        for game in games:
            display = game_display_name(game)
            values.append(display)
            self._display_to_id[display] = game.game_id
        self.game_combo.configure(values=values)
        if values:
            self.selected_game_var.set(values[0])
            self.status_var.set(f"Loaded {len(values)} installed game(s).")
            self._enqueue_log(f"Steam root: {root}")
            self._enqueue_log(f"Loaded {len(values)} game(s) from Steam.")
        else:
            self.selected_game_var.set("")
            self.status_var.set("No installed Steam games found.")
            self._enqueue_log("No installed Steam games detected.")
        self._sync_steam_to_db(games)

    def start_run(self) -> None:
        if self._worker and self._worker.is_alive():
            messagebox.showinfo("Running", "Assistant is already running.")
            return

        options = self._collect_options()
        if options is None:
            return

        self._set_running_state(True)
        self._enqueue_log(
            f"Starting mode={options.run_mode}, game_id={options.game_id}, overlay={options.overlay_enabled}, hotkeys={options.hotkeys_enabled}, ai={options.ai_advisor_enabled}, voice_volume={options.voice_volume:.2f}"
        )
        self._worker = Thread(target=self._run_worker, args=(options,), name="gwh-gui-worker", daemon=True)
        self._worker.start()

    def stop_run(self) -> None:
        if self._runtime_control is None:
            return
        self._runtime_control.stop()
        self._enqueue_log("Stop signal sent.")

    def _run_worker(self, options: GuiRunOptions) -> None:
        try:
            config = load_config(self.config_path)
            config.overlay_enabled = options.overlay_enabled
            config.hotkeys_enabled = options.hotkeys_enabled
            config.ai_advisor_enabled = options.ai_advisor_enabled
            config.voice_volume = options.voice_volume
            app = GuideAssistantApp(config)
            self._active_app = app

            if options.run_mode == "once":
                result = app.run_once(options.game_id)
                if result.observation is None:
                    self._enqueue_log("No frame captured.")
                else:
                    self._enqueue_log(f"Task: {result.observation.task_text or '<empty>'}")
                self._enqueue_log(result.hint_text or result.decision.speech_text)
                app.stop_session()
                app.db.close()
                return

            control = RuntimeControl(initial_detail_level=config.default_detail_level)
            self._runtime_control = control
            overlay = OverlayWindow(
                enabled=config.overlay_enabled,
                width=config.overlay_width,
                height=config.overlay_height,
                pos_x=config.overlay_pos_x,
                pos_y=config.overlay_pos_y,
            )
            hotkeys = HotkeyManager(control=control, enabled=config.hotkeys_enabled, status_handler=self._enqueue_log)
            app.run_loop(game_id=options.game_id, control=control, overlay=overlay, hotkeys=hotkeys)
        except Exception:
            self._enqueue_log("Unhandled error in GUI worker:")
            self._enqueue_log(traceback.format_exc())
        finally:
            self._active_app = None
            self._runtime_control = None
            self._queue.put(("done", ""))

    def _collect_options(self) -> GuiRunOptions | None:
        game_id = self._current_game_id()
        if not game_id:
            messagebox.showwarning("No game selected", "Please choose a Steam game or input manual game_id.")
            return None
        return GuiRunOptions(
            game_id=game_id,
            run_mode=self.mode_var.get().strip().lower(),
            overlay_enabled=self.overlay_var.get() == "1",
            hotkeys_enabled=self.hotkeys_var.get() == "1",
            ai_advisor_enabled=self.ai_advisor_var.get() == "1",
            voice_volume=clamp_volume(self.voice_volume_var.get() / 100.0),
        )

    def _set_running_state(self, running: bool) -> None:
        self.start_btn.configure(state="disabled" if running else "normal")
        self.stop_btn.configure(state="normal" if running else "disabled")

    def _sync_steam_to_db(self, games: list[SteamGame]) -> None:
        db = Database(self.base_config.db_path)
        db.init_schema()
        db.sync_steam_apps([game.as_db_record() for game in games])
        db.close()

    def _drain_queue(self) -> None:
        while True:
            try:
                kind, payload = self._queue.get_nowait()
            except Empty:
                break
            if kind == "log":
                self._append_log(payload)
            elif kind == "done":
                self._set_running_state(False)
                self.status_var.set("Idle")
                self._append_log("Run finished.")
        self.root.after(120, self._drain_queue)

    def _enqueue_log(self, text: str) -> None:
        self._queue.put(("log", text))

    def _append_log(self, text: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {text}\n"
        self.log_box.configure(state="normal")
        self.log_box.insert(END, line)
        self.log_box.see(END)
        self.log_box.configure(state="disabled")

    def _on_close(self) -> None:
        if self._runtime_control is not None:
            if not messagebox.askyesno("Exit", "Assistant is running. Stop and quit?"):
                return
            self._runtime_control.stop()
        self.root.destroy()

    def capture_scene_keyframe(self) -> None:
        from .capture.screen import ScreenCapture

        game_id = self._current_game_id()
        if not game_id:
            messagebox.showwarning("No game selected", "Please choose a game first.")
            return
        label = self.scene_label_var.get().strip()
        if not label:
            messagebox.showwarning("Missing label", "Please input a scene label before capture.")
            return
        frame = ScreenCapture().grab()
        if frame is None:
            messagebox.showerror("Capture failed", "Unable to capture current screen.")
            return
        db = Database(self.base_config.db_path)
        db.init_schema()
        manager = SceneKeyframeManager(
            db=db,
            keyframe_dir=self.base_config.scene_keyframe_dir,
            hash_size=self.base_config.scene_hash_size,
            default_distance_threshold=self.base_config.scene_match_distance_threshold,
        )
        try:
            record = manager.add_from_image(
                game_id=game_id,
                label=label,
                image=frame.image,
                action_text=self.scene_action_var.get().strip(),
            )
        finally:
            db.close()
        self._enqueue_log(
            f"Captured scene keyframe: label={record['label']} threshold={record['distance_threshold']} path={record['image_path']}"
        )
        messagebox.showinfo("Keyframe saved", f"Scene keyframe '{record['label']}' saved.")

    def list_scene_keyframes(self) -> None:
        game_id = self._current_game_id()
        if not game_id:
            messagebox.showwarning("No game selected", "Please choose a game first.")
            return
        db = Database(self.base_config.db_path)
        db.init_schema()
        manager = SceneKeyframeManager(
            db=db,
            keyframe_dir=self.base_config.scene_keyframe_dir,
            hash_size=self.base_config.scene_hash_size,
            default_distance_threshold=self.base_config.scene_match_distance_threshold,
        )
        records = manager.list_for_game(game_id)
        db.close()
        if not records:
            messagebox.showinfo("Scene Keyframes", "No scene keyframes found for this game.")
            return
        lines = []
        for item in records:
            lines.append(f"[{item['keyframe_id']}] {item['label']} (threshold={item['distance_threshold']})")
        messagebox.showinfo("Scene Keyframes", "\n".join(lines))

    def _current_game_id(self) -> str | None:
        return resolve_game_id(
            display_name=self.selected_game_var.get(),
            lookup=self._display_to_id,
            manual_game_id=self.manual_game_id_var.get(),
        )

    def apply_voice_volume(self) -> None:
        volume = clamp_volume(self.voice_volume_var.get() / 100.0)
        self.voice_volume_label_var.set(self._format_volume_percent(volume))
        app = self._active_app
        if app is None:
            self._enqueue_log(f"Voice volume set to {volume:.2f} (takes effect on next start).")
            return
        applied = app.voice.set_volume(volume)
        self._enqueue_log(f"Voice volume updated: {applied:.2f}")

    def _on_volume_change(self, _value: str) -> None:
        volume = clamp_volume(self.voice_volume_var.get() / 100.0)
        self.voice_volume_label_var.set(self._format_volume_percent(volume))

    @staticmethod
    def _format_volume_percent(volume: float) -> str:
        return f"{int(round(volume * 100)):d}%"


def launch_gui(config_path: str = "config/default.yaml") -> int:
    if not Path(config_path).exists():
        messagebox.showerror("Config missing", f"Config file not found: {config_path}")
        return 1
    app = GuideDesktopApp(config_path=config_path)
    app.start()
    return 0
