from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re

from .db import Database


@dataclass(slots=True)
class SceneMatch:
    keyframe_id: int
    game_id: str
    label: str
    action_text: str
    image_path: str
    distance: int
    max_distance: int
    confidence: float

    @property
    def state_id(self) -> str:
        return f"scene_{self.keyframe_id}"

    @property
    def hint_text(self) -> str:
        if self.action_text.strip():
            return self.action_text.strip()
        return f"场景识别：{self.label}"


class SceneKeyframeManager:
    def __init__(
        self,
        db: Database,
        keyframe_dir: str = "assets/keyframes",
        hash_size: int = 16,
        default_distance_threshold: int = 64,
    ) -> None:
        self.db = db
        self.keyframe_dir = Path(keyframe_dir)
        self.hash_size = max(4, hash_size)
        self.default_distance_threshold = max(1, default_distance_threshold)

    def add_from_image(
        self,
        game_id: str,
        label: str,
        image,
        action_text: str = "",
        distance_threshold: int | None = None,
    ) -> dict[str, str | int]:
        normalized_label = normalize_label(label)
        if not normalized_label:
            raise ValueError("Keyframe label cannot be empty.")
        game_dir = self.keyframe_dir / sanitize_file_component(game_id)
        game_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"{timestamp}_{sanitize_file_component(normalized_label)}.png"
        output_path = game_dir / file_name
        image.save(output_path)

        ahash = compute_ahash(image, self.hash_size)
        threshold = distance_threshold if distance_threshold is not None else self.default_distance_threshold
        threshold = max(1, int(threshold))
        keyframe_id = self.db.upsert_scene_keyframe(
            game_id=game_id,
            label=normalized_label,
            image_path=str(output_path),
            ahash=ahash,
            hash_size=self.hash_size,
            distance_threshold=threshold,
            action_text=action_text.strip(),
        )
        return {
            "keyframe_id": keyframe_id,
            "game_id": game_id,
            "label": normalized_label,
            "image_path": str(output_path),
            "distance_threshold": threshold,
            "action_text": action_text.strip(),
        }

    def add_from_path(
        self,
        game_id: str,
        label: str,
        image_path: str,
        action_text: str = "",
        distance_threshold: int | None = None,
    ) -> dict[str, str | int]:
        from PIL import Image  # type: ignore

        source = Path(image_path)
        if not source.exists():
            raise FileNotFoundError(f"Image not found: {source}")
        with Image.open(source) as img:
            image = img.convert("RGB")
            return self.add_from_image(
                game_id=game_id,
                label=label,
                image=image,
                action_text=action_text,
                distance_threshold=distance_threshold,
            )

    def list_for_game(self, game_id: str) -> list[dict[str, str | int]]:
        return self.db.get_scene_keyframes(game_id)


class SceneProgressMatcher:
    def __init__(
        self,
        db: Database,
        hash_size: int = 16,
        default_distance_threshold: int = 64,
    ) -> None:
        self.db = db
        self.hash_size = max(4, hash_size)
        self.default_distance_threshold = max(1, default_distance_threshold)

    def match(self, game_id: str, image) -> SceneMatch | None:
        keyframes = self.db.get_scene_keyframes(game_id)
        if not keyframes:
            return None
        frame_hash = compute_ahash(image, self.hash_size)
        best: SceneMatch | None = None

        for row in keyframes:
            keyframe_hash = str(row["ahash"])
            hash_size = int(row["hash_size"])
            if hash_size != self.hash_size:
                continue
            distance = hamming_distance_hex(frame_hash, keyframe_hash)
            max_distance = int(row["distance_threshold"] or self.default_distance_threshold)
            if distance > max_distance:
                continue
            confidence = scene_confidence(distance=distance, max_distance=max_distance)
            candidate = SceneMatch(
                keyframe_id=int(row["keyframe_id"]),
                game_id=game_id,
                label=str(row["label"]),
                action_text=str(row["action_text"] or ""),
                image_path=str(row["image_path"]),
                distance=distance,
                max_distance=max_distance,
                confidence=confidence,
            )
            if best is None or candidate.distance < best.distance:
                best = candidate
        return best


def compute_ahash(image, hash_size: int = 16) -> str:
    size = max(4, hash_size)
    gray = image.convert("L").resize((size, size))
    pixels = list(gray.getdata())
    if not pixels:
        return "0" * (size * size // 4)
    avg = sum(int(value) for value in pixels) / len(pixels)
    bits = "".join("1" if int(value) >= avg else "0" for value in pixels)
    width = size * size // 4
    return f"{int(bits, 2):0{width}x}"


def hamming_distance_hex(left: str, right: str) -> int:
    if not left or not right:
        return 999999
    try:
        return (int(left, 16) ^ int(right, 16)).bit_count()
    except ValueError:
        return 999999


def scene_confidence(distance: int, max_distance: int) -> float:
    if max_distance <= 0:
        return 0.0
    ratio = max(0.0, min(1.0, 1.0 - (distance / float(max_distance))))
    return round(min(0.95, 0.55 + ratio * 0.4), 4)


def normalize_label(label: str) -> str:
    return " ".join(label.strip().split())


def sanitize_file_component(value: str) -> str:
    normalized = normalize_label(value)
    safe = re.sub(r"[^a-zA-Z0-9_\-.]+", "_", normalized)
    return safe.strip("._") or "scene"

