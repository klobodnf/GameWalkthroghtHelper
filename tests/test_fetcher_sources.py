from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gamewalk_helper.guides.fetcher import GuideFetcher, parse_source_domains


class DummyDb:
    def get_cache(self, _cache_key: str):  # type: ignore[no-untyped-def]
        return None

    def set_cache(self, **_kwargs):  # type: ignore[no-untyped-def]
        return None


class FetcherSourceTests(unittest.TestCase):
    def test_parse_source_domains(self) -> None:
        self.assertEqual(
            parse_source_domains("gamersky.com, www.3dmgame.com ,steamcommunity.com"),
            ["gamersky.com", "3dmgame.com", "steamcommunity.com"],
        )
        self.assertEqual(
            parse_source_domains(["https://gamersky.com", "3dmgame.com", "3dmgame.com"]),
            ["gamersky.com", "3dmgame.com"],
        )

    def test_preferred_domains_are_prioritized(self) -> None:
        fetcher = GuideFetcher(
            db=DummyDb(),  # type: ignore[arg-type]
            preferred_domains=["gamersky.com", "3dmgame.com"],
            per_source_limit=1,
            max_candidates=3,
        )

        def fake_html(query: str) -> str:
            return query

        def fake_parse(html: str) -> list[dict[str, str]]:
            if "site:gamersky.com" in html:
                return [
                    {"url": "https://www.gamersky.com/guide/a", "title": "Gamersky A", "snippet": "step a"},
                    {"url": "https://www.gamersky.com/guide/b", "title": "Gamersky B", "snippet": "step b"},
                ]
            if "site:3dmgame.com" in html:
                return [
                    {"url": "https://www.3dmgame.com/gl/1", "title": "3DM 1", "snippet": "step c"},
                ]
            return [
                {"url": "https://example.com/guide/1", "title": "Other 1", "snippet": "step d"},
                {"url": "https://example.com/guide/2", "title": "Other 2", "snippet": "step e"},
            ]

        with patch("gamewalk_helper.guides.fetcher._duckduckgo_html", side_effect=fake_html), patch(
            "gamewalk_helper.guides.fetcher._parse_duckduckgo_results", side_effect=fake_parse
        ):
            candidates = fetcher._fetch_online_candidates(query="steam_1 walkthrough", task_text="go to village")

        self.assertEqual(len(candidates), 3)
        self.assertIn("gamersky.com", candidates[0].source_url)
        self.assertIn("3dmgame.com", candidates[1].source_url)
        self.assertIn("example.com", candidates[2].source_url)


if __name__ == "__main__":
    unittest.main()

