from __future__ import annotations

from hashlib import sha1
from html import unescape
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import json
import re

from ..db import Database
from ..models import GuideStepCandidate


class GuideFetcher:
    def __init__(self, db: Database, ttl_hours: int = 24) -> None:
        self.db = db
        self.ttl_hours = ttl_hours

    def get_candidate_steps(self, game_id: str, task_text: str) -> list[GuideStepCandidate]:
        query = self._build_query(game_id, task_text)
        cache_key = self._cache_key(game_id, query)
        cached = self.db.get_cache(cache_key)
        if cached is not None:
            return cached
        candidates = self._fetch_online_candidates(query=query, task_text=task_text)
        if not candidates and task_text.strip():
            candidates = [self._build_fallback_candidate(task_text)]
        if candidates:
            self.db.set_cache(
                cache_key=cache_key,
                game_id=game_id,
                query=query,
                steps=candidates,
                ttl_hours=self.ttl_hours,
            )
        return candidates

    @staticmethod
    def _build_query(game_id: str, task_text: str) -> str:
        base = f"{game_id} walkthrough guide"
        task = task_text.strip()
        if not task:
            return base
        return f"{base} {task}"

    @staticmethod
    def _cache_key(game_id: str, query: str) -> str:
        digest = sha1(f"{game_id}|{query}".encode("utf-8")).hexdigest()
        return f"{game_id}:{digest}"

    def _fetch_online_candidates(self, query: str, task_text: str) -> list[GuideStepCandidate]:
        html = _duckduckgo_html(query)
        if not html:
            return []
        results = _parse_duckduckgo_results(html)
        candidates: list[GuideStepCandidate] = []
        keywords = _extract_keywords(task_text)
        for index, item in enumerate(results[:4]):
            action_text = item["title"]
            if item["snippet"]:
                action_text = f"{item['title']}，{item['snippet']}"
            state_id = f"web_{index}_{sha1(action_text.encode('utf-8')).hexdigest()[:8]}"
            candidates.append(
                GuideStepCandidate(
                    state_id=state_id,
                    action_text=action_text,
                    text_keywords=keywords,
                    cv_keywords=[],
                    history_prior=max(0.3, 0.8 - index * 0.15),
                    priority=max(0, 50 - index * 10),
                    source_url=item["url"],
                )
            )
        return candidates

    @staticmethod
    def _build_fallback_candidate(task_text: str) -> GuideStepCandidate:
        action = f"继续推进当前目标：{task_text}"
        state_id = f"fallback_{sha1(action.encode('utf-8')).hexdigest()[:8]}"
        return GuideStepCandidate(
            state_id=state_id,
            action_text=action,
            text_keywords=_extract_keywords(task_text),
            history_prior=0.35,
            priority=20,
        )


def _duckduckgo_html(query: str) -> str:
    url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
    req = Request(url=url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=10) as response:
            return response.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _parse_duckduckgo_results(html: str) -> list[dict[str, str]]:
    title_pattern = re.compile(r'<a[^>]*class="result__a"[^>]*href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>')
    snippet_pattern = re.compile(r'<a[^>]*class="result__snippet"[^>]*>(?P<snippet>.*?)</a>')
    titles = title_pattern.findall(html)
    snippets = snippet_pattern.findall(html)
    results: list[dict[str, str]] = []
    for idx, (url, title_html) in enumerate(titles):
        title = _strip_tags(unescape(title_html))
        snippet = ""
        if idx < len(snippets):
            snippet = _strip_tags(unescape(snippets[idx]))
        results.append({"url": url, "title": title, "snippet": snippet})
    return results


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _extract_keywords(task_text: str) -> list[str]:
    task = task_text.strip()
    if not task:
        return []
    if " " not in task:
        return [task]
    words = [token for token in re.split(r"[\s,，。.!?:：;；/\\]+", task) if token]
    if not words:
        return [task]
    top = words[:4]
    compact = json.loads(json.dumps(top, ensure_ascii=False))
    return compact

