from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gamewalk_helper.gui import resolve_game_id


class GuiHelperTests(unittest.TestCase):
    def test_resolve_prefers_manual_game_id(self) -> None:
        game_id = resolve_game_id(
            display_name="Alien: Isolation (steam_214490)",
            lookup={"Alien: Isolation (steam_214490)": "steam_214490"},
            manual_game_id="custom_game",
        )
        self.assertEqual(game_id, "custom_game")

    def test_resolve_uses_display_lookup(self) -> None:
        game_id = resolve_game_id(
            display_name="Alien: Isolation (steam_214490)",
            lookup={"Alien: Isolation (steam_214490)": "steam_214490"},
            manual_game_id="",
        )
        self.assertEqual(game_id, "steam_214490")

    def test_resolve_returns_none_when_empty(self) -> None:
        game_id = resolve_game_id(display_name="", lookup={}, manual_game_id="")
        self.assertIsNone(game_id)


if __name__ == "__main__":
    unittest.main()

