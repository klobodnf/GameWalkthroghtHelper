from __future__ import annotations

import argparse

from .config import load_config
from .db import Database
from .hotkeys import HotkeyManager
from .pipeline import GuideAssistantApp
from .runtime_control import RuntimeControl
from .ui.overlay import OverlayWindow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gwh", description="Game walkthrough helper CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    init_db = sub.add_parser("init-db", help="Initialize local SQLite schema")
    init_db.add_argument("--config", default="config/default.yaml", help="Path to config file")

    once = sub.add_parser("run-once", help="Run one perception/guide cycle")
    once.add_argument("--config", default="config/default.yaml", help="Path to config file")
    once.add_argument("--game-id", required=True, help="Logical game identifier")

    loop = sub.add_parser("run-loop", help="Run continuous perception loop")
    loop.add_argument("--config", default="config/default.yaml", help="Path to config file")
    loop.add_argument("--game-id", required=True, help="Logical game identifier")
    loop.add_argument("--no-overlay", action="store_true", help="Disable floating overlay window")
    loop.add_argument("--no-hotkeys", action="store_true", help="Disable global hotkeys")

    return parser


def cmd_init_db(config_path: str) -> int:
    config = load_config(config_path)
    db = Database(config.db_path)
    db.init_schema()
    db.close()
    print(f"Database initialized: {config.db_path}")
    return 0


def cmd_run_once(config_path: str, game_id: str) -> int:
    config = load_config(config_path)
    app = GuideAssistantApp(config)
    result = app.run_once(game_id=game_id)
    if result.observation is None:
        print("No frame captured; check screen capture dependencies.")
    else:
        print(result.decision.speech_text)
    app.stop_session()
    app.db.close()
    return 0


def cmd_run_loop(config_path: str, game_id: str, no_overlay: bool, no_hotkeys: bool) -> int:
    config = load_config(config_path)
    app = GuideAssistantApp(config)
    control = RuntimeControl(initial_detail_level=config.default_detail_level)
    overlay_enabled = config.overlay_enabled and not no_overlay
    hotkeys_enabled = config.hotkeys_enabled and not no_hotkeys
    overlay = OverlayWindow(
        enabled=overlay_enabled,
        width=config.overlay_width,
        height=config.overlay_height,
        pos_x=config.overlay_pos_x,
        pos_y=config.overlay_pos_y,
    )
    hotkeys = HotkeyManager(control=control, enabled=hotkeys_enabled)
    app.run_loop(game_id=game_id, control=control, overlay=overlay, hotkeys=hotkeys)
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    command = args.command
    if command == "init-db":
        return cmd_init_db(args.config)
    if command == "run-once":
        return cmd_run_once(args.config, args.game_id)
    if command == "run-loop":
        return cmd_run_loop(args.config, args.game_id, args.no_overlay, args.no_hotkeys)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
