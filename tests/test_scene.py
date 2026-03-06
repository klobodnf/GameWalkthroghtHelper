from __future__ import annotations

from pathlib import Path
import tempfile
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gamewalk_helper.db import Database
from gamewalk_helper.scene import SceneProgressMatcher, compute_ahash, hamming_distance_hex


class FakeImage:
    def __init__(self, pixels: list[int], size: int) -> None:
        self._pixels = pixels
        self._size = size

    def convert(self, _mode: str) -> "FakeImage":
        return self

    def resize(self, size: tuple[int, int]) -> "FakeImage":
        if size == (self._size, self._size):
            return self
        # Basic nearest-neighbor style downsample for tests.
        target = size[0]
        step = max(1, self._size // max(1, target))
        sampled: list[int] = []
        for y in range(0, self._size, step):
            for x in range(0, self._size, step):
                sampled.append(self._pixels[y * self._size + x])
                if len(sampled) >= target * target:
                    break
            if len(sampled) >= target * target:
                break
        sampled.extend([0] * (target * target - len(sampled)))
        return FakeImage(sampled[: target * target], target)

    def getdata(self) -> list[int]:
        return list(self._pixels)


class SceneMatcherTests(unittest.TestCase):
    def test_hamming_distance_hex(self) -> None:
        self.assertEqual(hamming_distance_hex("0f", "0f"), 0)
        self.assertEqual(hamming_distance_hex("0f", "00"), 4)

    def test_match_scene_keyframe(self) -> None:
        pixels = [
            0,
            0,
            255,
            255,
            0,
            0,
            255,
            255,
            0,
            0,
            255,
            255,
            0,
            0,
            255,
            255,
        ]
        image = FakeImage(pixels, size=4)
        ahash = compute_ahash(image, hash_size=4)
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(str(Path(tmpdir) / "scene.db"))
            try:
                db.init_schema()
                db.upsert_scene_keyframe(
                    game_id="steam_1",
                    label="start_area",
                    image_path="assets/keyframes/start.png",
                    ahash=ahash,
                    hash_size=4,
                    distance_threshold=4,
                    action_text="Go to the gate",
                )
                matcher = SceneProgressMatcher(db=db, hash_size=4, default_distance_threshold=4)
                match = matcher.match("steam_1", image)
                self.assertIsNotNone(match)
                assert match is not None
                self.assertEqual(match.label, "start_area")
                self.assertEqual(match.hint_text, "Go to the gate")
                self.assertGreater(match.confidence, 0.8)
            finally:
                db.close()

    def test_no_match_when_distance_too_high(self) -> None:
        image_a = FakeImage(
            [
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                255,
                255,
                255,
                255,
                255,
                255,
                255,
                255,
            ],
            size=4,
        )
        image_b = FakeImage(
            [
                255,
                255,
                255,
                255,
                255,
                255,
                255,
                255,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            ],
            size=4,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(str(Path(tmpdir) / "scene.db"))
            try:
                db.init_schema()
                db.upsert_scene_keyframe(
                    game_id="steam_2",
                    label="all_black",
                    image_path="assets/keyframes/black.png",
                    ahash=compute_ahash(image_a, hash_size=4),
                    hash_size=4,
                    distance_threshold=1,
                    action_text="",
                )
                matcher = SceneProgressMatcher(db=db, hash_size=4, default_distance_threshold=1)
                self.assertIsNone(matcher.match("steam_2", image_b))
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
