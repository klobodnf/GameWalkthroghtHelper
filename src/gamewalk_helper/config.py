from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json


@dataclass(slots=True)
class AppConfig:
    db_path: str = "data/gamewalk.db"
    capture_fps: float = 1.0
    loop_interval_seconds: float = 1.0
    voice_cooldown_seconds: int = 30
    voice_volume: float = 0.8
    scene_match_enabled: bool = True
    scene_match_when_no_task: bool = True
    scene_hash_size: int = 16
    scene_match_distance_threshold: int = 64
    scene_confidence_threshold: float = 0.75
    scene_keyframe_dir: str = "assets/keyframes"
    confidence_strong_threshold: float = 0.65
    confidence_margin_threshold: float = 0.15
    query_ttl_hours: int = 24
    guide_source_domains: str = "gamersky.com,3dmgame.com,steamcommunity.com"
    guide_per_source_limit: int = 2
    guide_max_candidates: int = 8
    max_suggestions: int = 2
    roi_auto_detect: bool = True
    roi_min_score: float = 0.25
    roi_switch_margin: float = 0.08
    overlay_enabled: bool = True
    overlay_width: int = 560
    overlay_height: int = 220
    overlay_pos_x: int = 24
    overlay_pos_y: int = 24
    hotkeys_enabled: bool = True
    default_detail_level: int = 1
    task_roi: dict[str, int] | None = None
    template_dir: str = "assets/templates"


def load_config(path: str | None) -> AppConfig:
    if not path:
        return AppConfig()
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    raw = config_path.read_text(encoding="utf-8")
    data: dict[str, Any]
    if config_path.suffix.lower() == ".json":
        data = json.loads(raw)
    else:
        data = _load_yaml_like(raw)
    return AppConfig(**{k: v for k, v in data.items() if hasattr(AppConfig, k)})


def _load_yaml_like(raw: str) -> dict[str, Any]:
    try:
        import yaml  # type: ignore

        return yaml.safe_load(raw) or {}
    except Exception:
        parsed: dict[str, Any] = {}
        for line in raw.splitlines():
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            if ":" not in text:
                continue
            key, value = text.split(":", 1)
            parsed[key.strip()] = _coerce_scalar(value.strip())
        return parsed


def _coerce_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"null", "none"}:
        return None
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value
