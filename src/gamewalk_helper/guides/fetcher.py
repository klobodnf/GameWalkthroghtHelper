from __future__ import annotations

from hashlib import sha1
from html import unescape
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen
import json
import re

from ..db import Database
from ..models import GuideStepCandidate


class GuideFetcher:
    def __init__(
        self,
        db: Database,
        ttl_hours: int = 24,
        preferred_domains: str | list[str] | None = None,
        per_source_limit: int = 2,
        max_candidates: int = 8,
    ) -> None:
        self.db = db
        self.ttl_hours = ttl_hours
        self.preferred_domains = parse_source_domains(preferred_domains)
        self.per_source_limit = max(1, per_source_limit)
        self.max_candidates = max(2, max_candidates)

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

    def _cache_key(self, game_id: str, query: str) -> str:
        source_part = ",".join(self.preferred_domains) if self.preferred_domains else "default"
        seed = f"{game_id}|{query}|{source_part}|{self.per_source_limit}|{self.max_candidates}"
        digest = sha1(seed.encode("utf-8")).hexdigest()
        return f"{game_id}:{digest}"

    def _fetch_online_candidates(self, query: str, task_text: str) -> list[GuideStepCandidate]:
        candidates: list[GuideStepCandidate] = []
        seen_urls: set[str] = set()
        keywords = _extract_keywords(task_text)

        plans: list[tuple[str, str | None]] = []
        for domain in self.preferred_domains:
            plans.append((f"{query} site:{domain}", domain))
        plans.append((query, None))

        for search_query, scoped_domain in plans:
            html = _duckduckgo_html(search_query)
            if not html:
                continue
            results = _parse_duckduckgo_results(html)
            accepted = 0
            for item in results:
                source_url = _normalize_result_url(item["url"])
                if not source_url or source_url in seen_urls:
                    continue
                domain = _extract_domain(source_url)
                if scoped_domain and not _domain_matches(domain, scoped_domain):
                    continue
                seen_urls.add(source_url)

                rank = len(candidates)
                domain_rank = _domain_rank(domain, self.preferred_domains)
                action_text = item["title"]
                if item["snippet"]:
                    action_text = f"{item['title']}，{item['snippet']}"
                state_id = f"web_{rank}_{sha1(action_text.encode('utf-8')).hexdigest()[:8]}"
                candidates.append(
                    GuideStepCandidate(
                        state_id=state_id,
                        action_text=action_text,
                        text_keywords=keywords,
                        cv_keywords=[],
                        history_prior=_history_prior(rank=rank, domain_rank=domain_rank),
                        priority=_priority(rank=rank, domain_rank=domain_rank),
                        source_url=source_url,
                    )
                )
                accepted += 1
                if scoped_domain and accepted >= self.per_source_limit:
                    break
                if len(candidates) >= self.max_candidates:
                    break
            if len(candidates) >= self.max_candidates:
                break
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


def parse_source_domains(raw: str | list[str] | None) -> list[str]:
    if raw is None:
        return []
    values: list[str]
    if isinstance(raw, list):
        values = [str(item).strip() for item in raw]
    else:
        values = [token.strip() for token in raw.split(",")]
    normalized: list[str] = []
    for value in values:
        domain = _normalize_domain(value)
        if not domain:
            continue
        if domain not in normalized:
            normalized.append(domain)
    return normalized


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


def _normalize_result_url(url: str) -> str:
    if not url:
        return ""
    value = unescape(url.strip())
    if value.startswith("//"):
        value = f"https:{value}"
    parsed = urlparse(value)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        redirected = parse_qs(parsed.query).get("uddg", [""])[0]
        if redirected:
            value = unquote(redirected)
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return value


def _extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
    except Exception:
        return ""
    return _normalize_domain(parsed.netloc)


def _normalize_domain(value: str) -> str:
    lowered = value.strip().lower()
    if not lowered:
        return ""
    if lowered.startswith("http://") or lowered.startswith("https://"):
        lowered = urlparse(lowered).netloc
    if lowered.startswith("www."):
        lowered = lowered[4:]
    return lowered


def _domain_matches(domain: str, target: str) -> bool:
    norm_target = _normalize_domain(target)
    if not domain or not norm_target:
        return False
    return domain == norm_target or domain.endswith(f".{norm_target}")


def _domain_rank(domain: str, preferred_domains: list[str]) -> int:
    for index, preferred in enumerate(preferred_domains):
        if _domain_matches(domain, preferred):
            return index
    return len(preferred_domains) + 1


def _history_prior(rank: int, domain_rank: int) -> float:
    domain_bonus = max(0.0, 0.18 - domain_rank * 0.05)
    rank_penalty = rank * 0.05
    return max(0.25, min(0.95, 0.7 + domain_bonus - rank_penalty))


def _priority(rank: int, domain_rank: int) -> int:
    base = 50 - rank * 7
    domain_bonus = max(0, 12 - domain_rank * 4)
    return max(5, min(95, base + domain_bonus))

