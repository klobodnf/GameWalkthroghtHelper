from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys


@dataclass(slots=True)
class SteamGame:
    app_id: str
    name: str
    install_dir: str
    library_path: str

    @property
    def game_id(self) -> str:
        return f"steam_{self.app_id}"

    def as_db_record(self) -> dict[str, str]:
        return {
            "app_id": self.app_id,
            "name": self.name,
            "install_dir": self.install_dir,
            "library_path": self.library_path,
        }


def find_steam_root() -> Path | None:
    candidates: list[Path] = []
    registry_path = _read_steam_path_from_registry()
    if registry_path:
        candidates.append(registry_path)
    program_files_x86 = Path.home().drive + "\\Program Files (x86)\\Steam"
    program_files = Path.home().drive + "\\Program Files\\Steam"
    candidates.extend([Path(program_files_x86), Path(program_files)])
    local_appdata = Path.home() / "AppData" / "Local" / "Steam"
    candidates.append(local_appdata)
    for candidate in candidates:
        if candidate.exists() and (candidate / "steamapps").exists():
            return candidate
    return None


def scan_installed_games() -> tuple[Path | None, list[SteamGame]]:
    root = find_steam_root()
    if root is None:
        return None, []
    libraries = _read_library_paths(root)
    games_by_id: dict[str, SteamGame] = {}
    for library in libraries:
        steamapps = library / "steamapps"
        if not steamapps.exists():
            continue
        for manifest in steamapps.glob("appmanifest_*.acf"):
            app = _parse_manifest(manifest, library)
            if app is None:
                continue
            old = games_by_id.get(app.app_id)
            if old is None or (old.name.startswith("App ") and not app.name.startswith("App ")):
                games_by_id[app.app_id] = app
    games = sorted(games_by_id.values(), key=lambda item: (item.name.lower(), item.app_id))
    return root, games


def interactive_select_game(games: list[SteamGame], id_only: bool = False) -> SteamGame | None:
    if not games:
        return None

    _print_selection_header(games, id_only=id_only)
    for index, game in enumerate(games, start=1):
        print(f"{index:>3}. {game.name} (AppID: {game.app_id})", file=sys.stderr if id_only else sys.stdout)

    while True:
        prompt_target = sys.stderr if id_only else sys.stdout
        print("", file=prompt_target)
        print("请输入序号选择游戏（q 取消）: ", end="", file=prompt_target, flush=True)
        raw = input().strip()
        if not raw:
            continue
        if raw.lower() in {"q", "quit", "exit"}:
            return None
        if not raw.isdigit():
            print("输入无效，请输入数字序号。", file=prompt_target)
            continue
        idx = int(raw)
        if idx < 1 or idx > len(games):
            print("超出范围，请重新输入。", file=prompt_target)
            continue
        return games[idx - 1]


def _read_steam_path_from_registry() -> Path | None:
    try:
        import winreg
    except Exception:
        return None
    keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
    ]
    for hive, subkey, value_name in keys:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
                path = Path(str(value))
                if path.exists():
                    return path
        except OSError:
            continue
    return None


def _read_library_paths(root: Path) -> list[Path]:
    libraries = {root}
    library_file = root / "steamapps" / "libraryfolders.vdf"
    if not library_file.exists():
        return list(libraries)

    text = _safe_read_text(library_file)
    for match in re.finditer(r'"path"\s+"([^"]+)"', text):
        raw = match.group(1)
        path = Path(raw.replace("\\\\", "\\"))
        if path.exists():
            libraries.add(path)
    return sorted(libraries, key=lambda item: str(item).lower())


def _parse_manifest(manifest: Path, library_path: Path) -> SteamGame | None:
    text = _safe_read_text(manifest)
    app_id_match = re.search(r'"appid"\s+"([^"]+)"', text)
    name_match = re.search(r'"name"\s+"([^"]+)"', text)
    install_dir_match = re.search(r'"installdir"\s+"([^"]+)"', text)
    if not app_id_match:
        return None
    app_id = app_id_match.group(1).strip()
    name = name_match.group(1).strip() if name_match else f"App {app_id}"
    install_dir_name = install_dir_match.group(1).strip() if install_dir_match else ""
    install_dir = str(library_path / "steamapps" / "common" / install_dir_name) if install_dir_name else ""
    return SteamGame(
        app_id=app_id,
        name=name,
        install_dir=install_dir,
        library_path=str(library_path),
    )


def _safe_read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return path.read_text(encoding=encoding, errors="ignore")
        except Exception:
            continue
    return ""


def _print_selection_header(games: list[SteamGame], id_only: bool) -> None:
    target = sys.stderr if id_only else sys.stdout
    print(f"检测到 {len(games)} 个已安装 Steam 游戏：", file=target)
