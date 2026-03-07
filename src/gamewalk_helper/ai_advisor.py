from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os


@dataclass(slots=True)
class AdvisorContext:
    game_id: str
    base_hint: str
    task_text: str
    confidence: float
    state_id: str | None
    scene_label: str = ""
    alternatives: list[str] | None = None


class AIHintAdvisor:
    def __init__(
        self,
        enabled: bool = True,
        api_key_env: str = "OPENAI_API_KEY",
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: int = 15,
        max_tokens: int = 120,
        cooldown_seconds: int = 45,
    ) -> None:
        self.enabled = enabled
        self.api_key_env = api_key_env
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = max(5, int(timeout_seconds))
        self.max_tokens = max(32, int(max_tokens))
        self.cooldown_seconds = max(10, int(cooldown_seconds))
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

        api_key = os.getenv(self.api_key_env, "").strip()
        if not api_key:
            self._remember(ctx.state_id, fallback, now)
            return fallback

        remote = self._call_remote(ctx, api_key)
        hint = remote or fallback
        self._remember(ctx.state_id, hint, now)
        return hint

    def _call_remote(self, ctx: AdvisorContext, api_key: str) -> str:
        try:
            import requests  # type: ignore
        except Exception:
            return ""

        prompt = self._build_user_prompt(ctx)
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "max_tokens": self.max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a game walkthrough assistant. Output one concise next-step hint in Simplified Chinese.",
                },
                {"role": "user", "content": prompt},
            ],
        }
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=self.timeout_seconds)
            if response.status_code >= 400:
                return ""
            data = response.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            return content
        except Exception:
            return ""

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

