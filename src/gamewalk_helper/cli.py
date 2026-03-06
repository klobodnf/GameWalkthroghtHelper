from __future__ import annotations

import argparse

from .config import load_config
from .db import Database
from .gui import launch_gui
from .hotkeys import HotkeyManager
from .pipeline import GuideAssistantApp
from .runtime_control import RuntimeControl
from .scene import SceneKeyframeManager
from .steam import interactive_select_game, scan_installed_games
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

    steam_list = sub.add_parser("steam-list", help="List installed Steam games")
    steam_list.add_argument("--config", default="config/default.yaml", help="Path to config file")
    steam_list.add_argument("--json", action="store_true", help="Print as JSON")

    steam_select = sub.add_parser("steam-select", help="Choose an installed Steam game interactively")
    steam_select.add_argument("--config", default="config/default.yaml", help="Path to config file")
    steam_select.add_argument("--id-only", action="store_true", help="Print only selected game_id to stdout")

    gui = sub.add_parser("gui", help="Launch desktop GUI")
    gui.add_argument("--config", default="config/default.yaml", help="Path to config file")

    scene_add = sub.add_parser("scene-add-keyframe", help="Capture or import a scene keyframe for no-task mode")
    scene_add.add_argument("--config", default="config/default.yaml", help="Path to config file")
    scene_add.add_argument("--game-id", required=True, help="Logical game identifier")
    scene_add.add_argument("--label", required=True, help="Scene label (e.g., castle_gate)")
    scene_add.add_argument("--action-text", default="", help="Suggested action when this scene is matched")
    scene_add.add_argument("--threshold", type=int, default=None, help="Optional hamming distance threshold")
    scene_add.add_argument("--image-path", default="", help="Optional local image path. If empty, capture current screen.")

    scene_list = sub.add_parser("scene-list-keyframes", help="List scene keyframes for a game")
    scene_list.add_argument("--config", default="config/default.yaml", help="Path to config file")
    scene_list.add_argument("--game-id", required=True, help="Logical game identifier")

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


def cmd_steam_list(config_path: str, as_json: bool) -> int:
    import json

    config = load_config(config_path)
    db = Database(config.db_path)
    db.init_schema()
    root, games = scan_installed_games()
    db.sync_steam_apps([game.as_db_record() for game in games])
    if as_json:
        payload = {
            "steam_root": str(root) if root else "",
            "count": len(games),
            "games": [
                {
                    "game_id": game.game_id,
                    "app_id": game.app_id,
                    "name": game.name,
                    "install_dir": game.install_dir,
                    "library_path": game.library_path,
                }
                for game in games
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if root is None:
            print("Steam not found on this machine.")
        else:
            print(f"Steam root: {root}")
        if not games:
            print("No installed Steam games detected.")
        for index, game in enumerate(games, start=1):
            print(f"{index:>3}. {game.name} | app_id={game.app_id} | game_id={game.game_id}")
    db.close()
    return 0


def cmd_steam_select(config_path: str, id_only: bool) -> int:
    config = load_config(config_path)
    db = Database(config.db_path)
    db.init_schema()
    root, games = scan_installed_games()
    db.sync_steam_apps([game.as_db_record() for game in games])
    if root is None or not games:
        if not id_only:
            print("未检测到 Steam 已安装游戏。")
        db.close()
        return 1
    selected = interactive_select_game(games, id_only=id_only)
    if selected is None:
        if not id_only:
            print("已取消选择。")
        db.close()
        return 1
    db.upsert_game(game_id=selected.game_id, exe_name=selected.install_dir, window_pattern=selected.name, language="auto")
    if id_only:
        print(selected.game_id)
    else:
        print(f"已选择: {selected.name} ({selected.game_id})")
    db.close()
    return 0


def cmd_gui(config_path: str) -> int:
    return launch_gui(config_path=config_path)


def cmd_scene_add_keyframe(
    config_path: str,
    game_id: str,
    label: str,
    action_text: str,
    threshold: int | None,
    image_path: str,
) -> int:
    from .capture.screen import ScreenCapture

    config = load_config(config_path)
    db = Database(config.db_path)
    db.init_schema()
    manager = SceneKeyframeManager(
        db=db,
        keyframe_dir=config.scene_keyframe_dir,
        hash_size=config.scene_hash_size,
        default_distance_threshold=config.scene_match_distance_threshold,
    )
    try:
        if image_path.strip():
            record = manager.add_from_path(
                game_id=game_id,
                label=label,
                image_path=image_path.strip(),
                action_text=action_text,
                distance_threshold=threshold,
            )
        else:
            frame = ScreenCapture().grab()
            if frame is None:
                print("Unable to capture current screen. Please provide --image-path.")
                return 1
            record = manager.add_from_image(
                game_id=game_id,
                label=label,
                image=frame.image,
                action_text=action_text,
                distance_threshold=threshold,
            )
        print(
            f"Added scene keyframe: game_id={record['game_id']} label={record['label']} "
            f"threshold={record['distance_threshold']} path={record['image_path']}"
        )
        return 0
    finally:
        db.close()


def cmd_scene_list_keyframes(config_path: str, game_id: str) -> int:
    config = load_config(config_path)
    db = Database(config.db_path)
    db.init_schema()
    manager = SceneKeyframeManager(
        db=db,
        keyframe_dir=config.scene_keyframe_dir,
        hash_size=config.scene_hash_size,
        default_distance_threshold=config.scene_match_distance_threshold,
    )
    records = manager.list_for_game(game_id)
    db.close()
    if not records:
        print("No scene keyframes found.")
        return 0
    for item in records:
        print(
            f"- id={item['keyframe_id']} label={item['label']} "
            f"threshold={item['distance_threshold']} action={item['action_text']} path={item['image_path']}"
        )
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
    if command == "steam-list":
        return cmd_steam_list(args.config, args.json)
    if command == "steam-select":
        return cmd_steam_select(args.config, args.id_only)
    if command == "gui":
        return cmd_gui(args.config)
    if command == "scene-add-keyframe":
        return cmd_scene_add_keyframe(
            config_path=args.config,
            game_id=args.game_id,
            label=args.label,
            action_text=args.action_text,
            threshold=args.threshold,
            image_path=args.image_path,
        )
    if command == "scene-list-keyframes":
        return cmd_scene_list_keyframes(args.config, args.game_id)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
