from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import os


@dataclass(slots=True)
class AppConfig:
    db_path: str = "data/gamewalk.db"
    capture_fps: float = 1.0
    capture_batch_size: int = 3
    capture_batch_interval_seconds: float = 0.25
    loop_interval_seconds: float = 1.0
    voice_cooldown_seconds: int = 30
    voice_volume: float = 0.8
    voice_input_enabled: bool = False
    voice_input_language: str = "zh-CN"
    voice_input_wake_word: str = ""
    voice_input_listen_timeout_seconds: float = 1.5
    voice_input_phrase_time_limit_seconds: float = 3.0
    voice_input_error_backoff_seconds: float = 3.0
    stabilizer_enabled: bool = True
    stabilizer_window_size: int = 6
    stabilizer_stable_hits: int = 3
    ai_advisor_enabled: bool = True
    ai_advisor_provider: str = "openai"
    ai_advisor_protocol: str = ""
    ai_advisor_api_key_env: str = ""
    ai_advisor_model: str = ""
    ai_advisor_base_url: str = ""
    ai_advisor_request_path: str = ""
    ai_advisor_temperature: float = 0.2
    ai_advisor_timeout_seconds: int = 15
    ai_advisor_max_tokens: int = 120
    ai_advisor_cooldown_seconds: int = 45
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
        config = AppConfig()
        _apply_env_overrides(config)
        return config
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    raw = config_path.read_text(encoding="utf-8")
    data: dict[str, Any]
    if config_path.suffix.lower() == ".json":
        data = json.loads(raw)
    else:
        data = _load_yaml_like(raw)
    config = AppConfig(**{k: v for k, v in data.items() if hasattr(AppConfig, k)})
    _apply_env_overrides(config)
    return config


def _apply_env_overrides(config: AppConfig) -> None:
    overrides: dict[str, tuple[str, type]] = {
        "voice_input_enabled": ("GWH_VOICE_INPUT_ENABLED", bool),
        "voice_input_language": ("GWH_VOICE_INPUT_LANGUAGE", str),
        "voice_input_wake_word": ("GWH_VOICE_INPUT_WAKE_WORD", str),
        "voice_input_listen_timeout_seconds": ("GWH_VOICE_INPUT_LISTEN_TIMEOUT_SECONDS", float),
        "voice_input_phrase_time_limit_seconds": ("GWH_VOICE_INPUT_PHRASE_TIME_LIMIT_SECONDS", float),
        "voice_input_error_backoff_seconds": ("GWH_VOICE_INPUT_ERROR_BACKOFF_SECONDS", float),
        "ai_advisor_enabled": ("GWH_AI_ADVISOR_ENABLED", bool),
        "ai_advisor_provider": ("GWH_AI_ADVISOR_PROVIDER", str),
        "ai_advisor_protocol": ("GWH_AI_ADVISOR_PROTOCOL", str),
        "ai_advisor_api_key_env": ("GWH_AI_ADVISOR_API_KEY_ENV", str),
        "ai_advisor_model": ("GWH_AI_ADVISOR_MODEL", str),
        "ai_advisor_base_url": ("GWH_AI_ADVISOR_BASE_URL", str),
        "ai_advisor_request_path": ("GWH_AI_ADVISOR_REQUEST_PATH", str),
        "ai_advisor_temperature": ("GWH_AI_ADVISOR_TEMPERATURE", float),
        "ai_advisor_timeout_seconds": ("GWH_AI_ADVISOR_TIMEOUT_SECONDS", int),
        "ai_advisor_max_tokens": ("GWH_AI_ADVISOR_MAX_TOKENS", int),
        "ai_advisor_cooldown_seconds": ("GWH_AI_ADVISOR_COOLDOWN_SECONDS", int),
    }
    for attr, (env_name, expected_type) in overrides.items():
        raw = os.getenv(env_name, "").strip()
        if not raw:
            continue
        value = _parse_env_value(raw, expected_type)
        if value is None:
            continue
        setattr(config, attr, value)


def _parse_env_value(raw: str, expected_type: type) -> Any:
    if expected_type is str:
        return raw
    if expected_type is bool:
        lowered = raw.lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
        return None
    if expected_type is int:
        try:
            return int(raw)
        except ValueError:
            return None
    if expected_type is float:
        try:
            return float(raw)
        except ValueError:
            return None
    return None


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
    if len(value) >= 2 and ((value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'"))):
        value = value[1:-1]
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
