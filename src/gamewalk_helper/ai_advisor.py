from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
from urllib.parse import urlencode


@dataclass(slots=True)
class AdvisorContext:
    game_id: str
    base_hint: str
    task_text: str
    confidence: float
    state_id: str | None
    scene_label: str = ""
    alternatives: list[str] | None = None


@dataclass(frozen=True, slots=True)
class ProviderPreset:
    protocol: str
    base_url: str
    model: str
    api_key_env: str
    request_path: str
    requires_api_key: bool = True


_PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    "openai": ProviderPreset(
        protocol="openai_chat",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        request_path="/chat/completions",
    ),
    "kimi": ProviderPreset(
        protocol="openai_chat",
        base_url="https://api.moonshot.cn/v1",
        model="moonshot-v1-8k",
        api_key_env="KIMI_API_KEY",
        request_path="/chat/completions",
    ),
    "deepseek": ProviderPreset(
        protocol="openai_chat",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
        api_key_env="DEEPSEEK_API_KEY",
        request_path="/chat/completions",
    ),
    "qwen": ProviderPreset(
        protocol="openai_chat",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen-plus",
        api_key_env="DASHSCOPE_API_KEY",
        request_path="/chat/completions",
    ),
    "zhipu": ProviderPreset(
        protocol="openai_chat",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        model="glm-4-plus",
        api_key_env="ZHIPUAI_API_KEY",
        request_path="/chat/completions",
    ),
    "openrouter": ProviderPreset(
        protocol="openai_chat",
        base_url="https://openrouter.ai/api/v1",
        model="openai/gpt-4o-mini",
        api_key_env="OPENROUTER_API_KEY",
        request_path="/chat/completions",
    ),
    "xai": ProviderPreset(
        protocol="openai_chat",
        base_url="https://api.x.ai/v1",
        model="grok-2-latest",
        api_key_env="XAI_API_KEY",
        request_path="/chat/completions",
    ),
    "anthropic": ProviderPreset(
        protocol="anthropic_messages",
        base_url="https://api.anthropic.com/v1",
        model="claude-3-5-haiku-latest",
        api_key_env="ANTHROPIC_API_KEY",
        request_path="/messages",
    ),
    "gemini": ProviderPreset(
        protocol="gemini_generate",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        model="gemini-1.5-flash",
        api_key_env="GOOGLE_API_KEY",
        request_path="",
    ),
    "ollama": ProviderPreset(
        protocol="ollama_chat",
        base_url="http://127.0.0.1:11434",
        model="qwen2.5:7b",
        api_key_env="",
        request_path="/api/chat",
        requires_api_key=False,
    ),
}

_PROVIDER_ALIASES: dict[str, str] = {
    "openai_compatible": "openai",
    "moonshot": "kimi",
    "claude": "anthropic",
    "google": "gemini",
    "local": "ollama",
}

_DEFAULT_PRESET = _PROVIDER_PRESETS["openai"]


def list_supported_providers() -> list[str]:
    return sorted(_PROVIDER_PRESETS.keys())


def normalize_provider(provider: str | None) -> str:
    raw = (provider or "").strip().lower()
    if not raw:
        return "openai"
    if raw in _PROVIDER_PRESETS:
        return raw
    return _PROVIDER_ALIASES.get(raw, raw)


class AIHintAdvisor:
    def __init__(
        self,
        enabled: bool = True,
        provider: str = "openai",
        protocol: str = "",
        api_key_env: str = "",
        model: str = "",
        base_url: str = "",
        request_path: str = "",
        temperature: float = 0.2,
        timeout_seconds: int = 15,
        max_tokens: int = 120,
        cooldown_seconds: int = 45,
    ) -> None:
        self.enabled = enabled
        self.provider = normalize_provider(provider)
        preset = _PROVIDER_PRESETS.get(self.provider, _DEFAULT_PRESET)
        self.protocol = (protocol or preset.protocol).strip().lower()
        self.api_key_env = (api_key_env or preset.api_key_env).strip()
        self.model = (model or preset.model).strip()
        self.base_url = (base_url or preset.base_url).strip().rstrip("/")
        self.request_path = (request_path or preset.request_path).strip()
        self.temperature = _clamp_temperature(temperature)
        self.timeout_seconds = max(5, int(timeout_seconds))
        self.max_tokens = max(32, int(max_tokens))
        self.cooldown_seconds = max(10, int(cooldown_seconds))
        self.requires_api_key = preset.requires_api_key
        self._last_state_id: str | None = None
        self._last_hint: str = ""
        self._last_time: datetime | None = None

    def suggest(self, ctx: AdvisorContext) -> str:
        fallback = self._local_hint(ctx)
        if not self.enabled:
            return fallback

        now = datetime.now(timezone.utc)
        if self._last_time is not None and ctx.state_id == self._last_state_id:
            if now - self._last_time < timedelta(seconds=self.cooldown_seconds):
                return self._last_hint or fallback

        api_key = os.getenv(self.api_key_env, "").strip() if self.api_key_env else ""
        if self.requires_api_key and not api_key:
            self._remember(ctx.state_id, fallback, now)
            return fallback

        remote = self._call_remote(ctx, api_key=api_key)
        hint = remote or fallback
        self._remember(ctx.state_id, hint, now)
        return hint

    def _call_remote(self, ctx: AdvisorContext, api_key: str) -> str:
        try:
            import requests  # type: ignore
        except Exception:
            return ""

        prompt = self._build_user_prompt(ctx)
        system_prompt = "You are a game walkthrough assistant. Output one concise next-step hint in Simplified Chinese."
        try:
            if self.protocol == "anthropic_messages":
                return self._call_anthropic(requests, system_prompt, prompt, api_key)
            if self.protocol == "gemini_generate":
                return self._call_gemini(requests, system_prompt, prompt, api_key)
            if self.protocol == "ollama_chat":
                return self._call_ollama(requests, system_prompt, prompt)
            return self._call_openai_compatible(requests, system_prompt, prompt, api_key)
        except Exception:
            return ""

    def _call_openai_compatible(self, requests, system_prompt: str, prompt: str, api_key: str) -> str:  # type: ignore[no-untyped-def]
        url = _join_url(self.base_url, self.request_path or "/chat/completions")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        }
        response = requests.post(url, headers=headers, json=payload, timeout=self.timeout_seconds)
        if response.status_code >= 400:
            return ""
        return _extract_openai_message(response.json())

    def _call_anthropic(self, requests, system_prompt: str, prompt: str, api_key: str) -> str:  # type: ignore[no-untyped-def]
        url = _join_url(self.base_url, self.request_path or "/messages")
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}],
        }
        response = requests.post(url, headers=headers, json=payload, timeout=self.timeout_seconds)
        if response.status_code >= 400:
            return ""
        data = response.json()
        blocks = data.get("content", [])
        for item in blocks:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text", "")).strip()
                if text:
                    return text
        return ""

    def _call_gemini(self, requests, system_prompt: str, prompt: str, api_key: str) -> str:  # type: ignore[no-untyped-def]
        path = self.request_path or f"/models/{self.model}:generateContent"
        base_url = _join_url(self.base_url, path)
        query = urlencode({"key": api_key})
        url = f"{base_url}?{query}" if "?" not in base_url else f"{base_url}&{query}"
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
            },
        }
        response = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=self.timeout_seconds)
        if response.status_code >= 400:
            return ""
        data = response.json()
        candidates = data.get("candidates", [])
        for candidate in candidates:
            content = candidate.get("content", {})
            parts = content.get("parts", [])
            for part in parts:
                text = str(part.get("text", "")).strip()
                if text:
                    return text
        return ""

    def _call_ollama(self, requests, system_prompt: str, prompt: str) -> str:  # type: ignore[no-untyped-def]
        url = _join_url(self.base_url, self.request_path or "/api/chat")
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "options": {"temperature": self.temperature},
        }
        response = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=self.timeout_seconds)
        if response.status_code >= 400:
            return ""
        data = response.json()
        message = data.get("message", {})
        return str(message.get("content", "")).strip()

    def _build_user_prompt(self, ctx: AdvisorContext) -> str:
        alternatives = ctx.alternatives or []
        alt_text = "；".join(alternatives[:2])
        lines = [
            f"游戏ID: {ctx.game_id}",
            f"当前状态ID: {ctx.state_id or 'unknown'}",
            f"任务文本: {ctx.task_text or '无'}",
            f"场景标签: {ctx.scene_label or '无'}",
            f"规则提示: {ctx.base_hint}",
            f"置信度: {ctx.confidence:.2f}",
            f"候选步骤: {alt_text or '无'}",
            "请给出下一步操作提示（1句话，20字以内，直接可执行）。",
        ]
        return "\n".join(lines)

    def _local_hint(self, ctx: AdvisorContext) -> str:
        hint = ctx.base_hint.strip()
        if not hint:
            if ctx.scene_label:
                return f"检测到场景 {ctx.scene_label}，请按当前路线继续推进。"
            return "继续观察当前画面并尝试推进主线。"
        if ctx.confidence < 0.45:
            return f"低置信度建议：{hint}"
        return hint

    def _remember(self, state_id: str | None, hint: str, now: datetime) -> None:
        self._last_state_id = state_id
        self._last_hint = hint
        self._last_time = now


def _join_url(base_url: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not base_url:
        return path
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _extract_openai_message(data: dict) -> str:
    choices = data.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    if not isinstance(message, dict):
        return ""
    return str(message.get("content", "")).strip()


def _clamp_temperature(value: float) -> float:
    if value <= 0.0:
        return 0.0
    if value >= 1.5:
        return 1.5
    return float(value)
