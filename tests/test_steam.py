from __future__ import annotations

from pathlib import Path
import tempfile
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import gamewalk_helper.steam as steam


class SteamScanTests(unittest.TestCase):
    def test_scan_installed_games_from_libraryfolders(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "Steam"
            lib2 = Path(tmpdir) / "SteamLibrary2"
            (root / "steamapps").mkdir(parents=True)
            (lib2 / "steamapps" / "common" / "SomeGame").mkdir(parents=True)

            library_vdf = """
"libraryfolders"
{
  "0"
  {
    "path" "C:\\\\Fake"
  }
  "1"
  {
    "path" "%s"
  }
}
""" % str(lib2).replace("\\", "\\\\")
            (root / "steamapps" / "libraryfolders.vdf").write_text(library_vdf, encoding="utf-8")

            manifest = """
"AppState"
{
  "appid"    "12345"
  "name"     "Test Game"
  "installdir" "SomeGame"
}
"""
            (lib2 / "steamapps" / "appmanifest_12345.acf").write_text(manifest, encoding="utf-8")

            original = steam.find_steam_root
            try:
                steam.find_steam_root = lambda: root  # type: ignore[assignment]
                detected_root, games = steam.scan_installed_games()
            finally:
                steam.find_steam_root = original  # type: ignore[assignment]

            self.assertEqual(detected_root, root)
            self.assertEqual(len(games), 1)
            self.assertEqual(games[0].app_id, "12345")
            self.assertEqual(games[0].name, "Test Game")
            self.assertTrue(games[0].install_dir.endswith("SomeGame"))
            self.assertEqual(games[0].game_id, "steam_12345")

    def test_parse_manifest_returns_none_when_missing_appid(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest = root / "bad.acf"
            manifest.write_text('"AppState" { "name" "x" }', encoding="utf-8")
            game = steam._parse_manifest(manifest, root)  # noqa: SLF001
            self.assertIsNone(game)


if __name__ == "__main__":
    unittest.main()

