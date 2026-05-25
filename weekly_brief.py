#!/usr/bin/env python3
"""Daily AI/developer issue brief generator.

Collects recent links from public feeds, Hacker News, and selected GitHub
releases, then writes a readable one-page HTML brief. If GEMINI_API_KEY is set,
the collected evidence is synthesized into Korean before rendering.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo


DEFAULT_QUERIES = [
    "AI agent",
    "LLM",
    "Claude Code",
    "Cursor IDE",
    "developer tools",
    "MCP",
    "OpenAI",
    "Anthropic",
    "GitHub Copilot",
]

DEFAULT_FEEDS = [
    "https://openai.com/news/rss.xml",
    "https://www.anthropic.com/news/rss.xml",
    "https://github.blog/feed/",
    "https://hnrss.org/newest?q=AI",
    "https://hnrss.org/newest?q=developer%20tools",
    "https://hnrss.org/newest?q=programming",
    "https://www.latent.space/feed",
    "https://simonwillison.net/atom/everything/",
]

DEFAULT_GITHUB_REPOS = [
    "openai/openai-python",
    "anthropics/anthropic-sdk-python",
    "microsoft/vscode",
    "github/copilot.vim",
    "modelcontextprotocol/python-sdk",
    "modelcontextprotocol/typescript-sdk",
    "langchain-ai/langchain",
    "vercel/ai",
    "continuedev/continue",
]

DEFAULT_OPPORTUNITY_SOURCES = [
    "https://linkareer.com/",
    "https://www.wevity.com/",
    "https://www.contestkorea.com/",
    "https://www.thinkcontest.com/thinkgood/index.do",
]

DEFAULT_OPPORTUNITY_KEYWORDS = [
    "hackathon",
    "developer",
    "software",
    "programming",
    "coding",
    "cloud",
    "security",
    "startup",
    "해커톤",
    "개발",
    "개발자",
    "소프트웨어",
    "프로그램",
    "프로그래밍",
    "코딩",
    "인공지능",
    "데이터",
    "클라우드",
    "보안",
    "알고리즘",
    "오픈소스",
    "웹",
    "모바일",
    "앱",
    "게임",
    "공학",
    "창업",
    "스타트업",
    "AI",
    "IT",
    "SW",
]

DEFAULT_OPPORTUNITY_TYPE_KEYWORDS = [
    "hackathon",
    "contest",
    "competition",
    "challenge",
    "해커톤",
    "공모전",
    "경진대회",
    "대회",
    "아이디어톤",
]

DEFAULT_OPPORTUNITY_EXCLUDE_KEYWORDS = [
    "채용",
    "인턴",
    "알바",
    "프리랜서",
    "서포터즈",
    "봉사",
    "기자단",
    "체험단",
]

USER_AGENT = "weekly-ai-dev-brief/1.0 (+personal automation)"


@dataclass(frozen=True)
class Item:
    title: str
    url: str
    source: str
    published: dt.datetime
    summary: str = ""
    score: int = 0
    kind: str = "link"


@dataclass(frozen=True)
class Opportunity:
    title: str
    url: str
    source: str
    deadline: str = ""
    summary: str = ""
    score: int = 0


@dataclass(frozen=True)
class GeneratedBrief:
    stamp: str
    timezone: str
    period_start: str
    period_end: str
    items_count: int
    markdown: str
    html: str


def csv_env(name: str, default: Iterable[str]) -> list[str]:
    value = os.getenv(name, "").strip()
    if not value:
        return list(default)
    return [part.strip() for part in value.split(",") if part.strip()]


def request_json(url: str, headers: dict[str, str] | None = None) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def request_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_date(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    value = value.strip()
    candidates = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
    ]
    for fmt in candidates:
        try:
            parsed = dt.datetime.strptime(value, fmt)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
        except ValueError:
            pass
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def clean_text(value: str | None, limit: int = 360) -> str:
    if not value:
        return ""
    text = " ".join(html.unescape(value).split())
    for tag in ("<p>", "</p>", "<br>", "<br/>", "<br />"):
        text = text.replace(tag, " ")
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0] + "..."


def strip_html(value: str, limit: int = 500) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", value)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return clean_text(text, limit)


def source_name(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    return {
        "linkareer.com": "Linkareer",
        "wevity.com": "Wevity",
        "contestkorea.com": "Contest Korea",
        "thinkcontest.com": "Thinkgood",
    }.get(host, host or url)


def canonical_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    tracking_prefixes = ("utm_",)
    tracking_names = {"gad_source", "gad_campaignid", "gbraid", "gclid", "fbclid"}
    query = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if key not in tracking_names and not key.startswith(tracking_prefixes)
    ]
    return urllib.parse.urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urllib.parse.urlencode(query),
            "",
        )
    ).rstrip("?")


def has_dev_keyword(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def extract_deadline(text: str) -> str:
    patterns = [
        r"D\s*-\s*\d+",
        r"\d{4}[./-]\d{1,2}[./-]\d{1,2}\s*(?:까지|마감)?",
        r"\d{1,2}[./-]\d{1,2}\s*(?:까지|마감)?",
        r"(?:접수|모집|신청)\s*(?:기간|마감)?\s*[:：]?\s*[^.。|]{0,40}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return clean_text(match.group(0), 80)
    return ""


def opportunity_score(title: str, context: str, keywords: list[str]) -> int:
    haystack = f"{title} {context}".lower()
    score = sum(8 for keyword in keywords if keyword.lower() in haystack)
    if re.search(r"D\s*-\s*(\d+)", context, flags=re.IGNORECASE):
        days = int(re.search(r"D\s*-\s*(\d+)", context, flags=re.IGNORECASE).group(1))  # type: ignore[union-attr]
        score += max(0, 40 - min(days, 40))
    if any(word in haystack for word in ("해커톤", "hackathon", "개발자", "소프트웨어", "ai", "인공지능")):
        score += 25
    return score


def extract_opportunities_from_html(
    html_text: str,
    base_url: str,
    source: str,
    keywords: list[str],
    type_keywords: list[str],
    exclude_keywords: list[str],
    limit: int,
) -> list[Opportunity]:
    opportunities: list[Opportunity] = []
    anchor_pattern = re.compile(
        r"(?is)<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>"
    )
    for match in anchor_pattern.finditer(html_text):
        href = html.unescape(match.group(1)).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        title = strip_html(match.group(2), 160)
        if len(title) < 6:
            continue

        url = canonical_url(urllib.parse.urljoin(base_url, href))
        if not url.startswith(("http://", "https://")):
            continue

        after = html_text[match.end() : min(len(html_text), match.end() + 420)]
        context = strip_html(match.group(2) + after, 420)
        filter_text = f"{title} {context}"
        if has_dev_keyword(title, exclude_keywords):
            continue
        if not has_dev_keyword(title, type_keywords):
            continue
        if not has_dev_keyword(title, keywords) and not has_dev_keyword(title, ["해커톤", "hackathon"]):
            continue

        summary = context
        if title in summary:
            summary = clean_text(summary.replace(title, " "), 260)
        opportunities.append(
            Opportunity(
                title=title,
                url=url,
                source=source,
                deadline=extract_deadline(context),
                summary=summary,
                score=opportunity_score(title, context, keywords),
            )
        )

    return sorted(opportunities, key=lambda item: item.score, reverse=True)[:limit]


def fetch_opportunities(
    source_urls: list[str],
    keywords: list[str],
    type_keywords: list[str],
    exclude_keywords: list[str],
    limit_per_source: int = 12,
) -> list[Opportunity]:
    collected: list[Opportunity] = []
    for source_url in source_urls:
        clean_source_url = canonical_url(source_url)
        try:
            html_text = request_text(clean_source_url)
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
        collected.extend(
            extract_opportunities_from_html(
                html_text,
                clean_source_url,
                source_name(clean_source_url),
                keywords,
                type_keywords,
                exclude_keywords,
                limit_per_source,
            )
        )

    seen: set[str] = set()
    unique: list[Opportunity] = []
    for item in sorted(collected, key=lambda x: x.score, reverse=True):
        key = item.url.split("?")[0].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def opportunities_markdown(opportunities: list[Opportunity], limit: int = 12) -> str:
    if not opportunities:
        return "\n\n## 개발자 해커톤·공모전\n\n- 이번 수집에서는 개발자에게 맞는 해커톤/공모전을 찾지 못했습니다.\n"

    lines = ["", "## 개발자 해커톤·공모전", ""]
    for item in opportunities[:limit]:
        meta = f"{item.source}"
        if item.deadline:
            meta += f", {item.deadline}"
        summary = f" {item.summary}" if item.summary else ""
        lines.append(f"- [{item.title}]({item.url}) - {meta}.{summary}")
    return "\n".join(lines) + "\n"


def fetch_rss_items(feed_urls: list[str], start: dt.datetime, end: dt.datetime) -> list[Item]:
    items: list[Item] = []
    for feed_url in feed_urls:
        try:
            root = ET.fromstring(request_text(feed_url))
        except (ET.ParseError, urllib.error.URLError, TimeoutError, OSError):
            continue

        channel_title = root.findtext("./channel/title") or urllib.parse.urlparse(feed_url).netloc
        rss_entries = root.findall("./channel/item")
        atom_entries = root.findall("{http://www.w3.org/2005/Atom}entry")

        for entry in rss_entries:
            published = parse_date(entry.findtext("pubDate") or entry.findtext("date"))
            if not published or not (start <= published.astimezone(dt.timezone.utc) <= end):
                continue
            title = clean_text(entry.findtext("title"), 180)
            url = entry.findtext("link") or feed_url
            summary = clean_text(entry.findtext("description"))
            items.append(Item(title, url, channel_title, published, summary, kind="feed"))

        for entry in atom_entries:
            published = parse_date(
                entry.findtext("{http://www.w3.org/2005/Atom}updated")
                or entry.findtext("{http://www.w3.org/2005/Atom}published")
            )
            if not published or not (start <= published.astimezone(dt.timezone.utc) <= end):
                continue
            title = clean_text(entry.findtext("{http://www.w3.org/2005/Atom}title"), 180)
            link = entry.find("{http://www.w3.org/2005/Atom}link")
            url = link.attrib.get("href", feed_url) if link is not None else feed_url
            summary = clean_text(entry.findtext("{http://www.w3.org/2005/Atom}summary"))
            items.append(Item(title, url, channel_title, published, summary, kind="feed"))

    return items


def fetch_hn_items(queries: list[str], start: dt.datetime, end: dt.datetime) -> list[Item]:
    items: list[Item] = []
    start_i = int(start.timestamp())
    end_i = int(end.timestamp())
    for query in queries:
        params = urllib.parse.urlencode(
            {
                "query": query,
                "tags": "story",
                "hitsPerPage": 20,
                "numericFilters": f"created_at_i>{start_i},created_at_i<{end_i}",
            }
        )
        url = f"https://hn.algolia.com/api/v1/search?{params}"
        try:
            payload = request_json(url)
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            continue
        for hit in payload.get("hits", []):  # type: ignore[union-attr]
            title = clean_text(hit.get("title") or hit.get("story_title"), 180)
            story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            published = parse_date(hit.get("created_at"))
            if not title or not published:
                continue
            points = int(hit.get("points") or 0)
            comments = int(hit.get("num_comments") or 0)
            items.append(
                Item(
                    title=title,
                    url=story_url,
                    source=f"Hacker News / {query}",
                    published=published,
                    summary=f"{points} points, {comments} comments",
                    score=points + comments * 2,
                    kind="hn",
                )
            )
    return items


def fetch_github_releases(repos: list[str], start: dt.datetime, end: dt.datetime) -> list[Item]:
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"

    items: list[Item] = []
    for repo in repos:
        url = f"https://api.github.com/repos/{repo}/releases?per_page=10"
        try:
            payload = request_json(url, headers=headers)
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, list):
            continue
        for release in payload:
            published = parse_date(release.get("published_at"))
            if not published or not (start <= published.astimezone(dt.timezone.utc) <= end):
                continue
            name = clean_text(release.get("name") or release.get("tag_name"), 180)
            body = clean_text(release.get("body"), 420)
            items.append(
                Item(
                    title=f"{repo}: {name}",
                    url=release.get("html_url") or f"https://github.com/{repo}/releases",
                    source="GitHub Releases",
                    published=published,
                    summary=body,
                    score=50,
                    kind="github",
                )
            )
    return items


def dedupe_items(items: Iterable[Item]) -> list[Item]:
    seen: set[str] = set()
    unique: list[Item] = []
    for item in sorted(items, key=lambda x: (x.score, x.published), reverse=True):
        key = item.url.split("?")[0].rstrip("/")
        if key in seen or not item.title:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def evidence_block(items: list[Item], tz: ZoneInfo, limit: int = 45) -> str:
    lines = []
    for index, item in enumerate(items[:limit], 1):
        local_date = item.published.astimezone(tz).strftime("%Y-%m-%d")
        lines.append(
            f"{index}. [{item.kind}] {item.title}\n"
            f"   source: {item.source} | date: {local_date} | score: {item.score}\n"
            f"   url: {item.url}\n"
            f"   note: {item.summary or 'no summary'}"
        )
    return "\n".join(lines)


def synthesis_prompt(items: list[Item], start: dt.datetime, end: dt.datetime, tz: ZoneInfo) -> str:
    return f"""
You are writing a concise Korean daily briefing for one software developer.
Use only the evidence below. Do not invent facts.

Period: {start.astimezone(tz).strftime('%Y-%m-%d %H:%M')} to {end.astimezone(tz).strftime('%Y-%m-%d %H:%M')} ({tz.key})

Write the output in Korean Markdown with exactly these sections:

## 오늘의 핵심
- 4-5 bullets only.
- Each bullet must explain why it matters in one compact sentence.
- Use one inline Markdown link per bullet.

## 자세히 보기
### AI
- 3-5 bullets about model, product, research, policy, or AI company news.
### 개발 이슈
- 3-5 bullets about platform, language, framework, security, infra, or ecosystem changes.
### 개발 도구
- 3-5 bullets about tools worth trying or watching.

## 빠르게 열어볼 링크
- 6-8 bullets, each starting with a Markdown link and then a short reason.

## 신뢰도 메모
- 1-3 bullets about source gaps, rumors, weak evidence, or duplicated source patterns.

Rules:
- Do not repeat the same article, link, title, or claim across sections.
- If an item appears in "오늘의 핵심", do not mention it again in "자세히 보기".
- Do not append a bare English title after a Korean sentence. Put the title inside the Markdown link instead.
- Prefer fewer, stronger items over long exhaustive lists.
- Keep the full brief under 22 bullets.
- Skip low-signal rumors unless the evidence itself is the point.
- Use normal Markdown only: headings, bullets, numbered lists, bold, and inline links.
- Do not use footnotes or citation markers such as [^1], [1], or "source 1".
- Every concrete claim should include an inline Markdown link like [title](https://example.com), not a footnote.

Evidence:
{evidence_block(items, tz)}
""".strip()


def gemini_synthesis(items: list[Item], start: dt.datetime, end: dt.datetime, tz: ZoneInfo) -> str | None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    body = json.dumps(
        {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": synthesis_prompt(items, start, end, tz)}],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 3000,
            },
        }
    ).encode("utf-8")
    encoded_model = urllib.parse.quote(model, safe="")
    request = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{encoded_model}:generateContent",
        data=body,
        method="POST",
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return f"## 신뢰도 메모\n\nGemini 요약 생성에 실패했습니다: `{exc}`\n"

    chunks: list[str] = []
    for candidate in payload.get("candidates", []):
        content = candidate.get("content") or {}
        for part in content.get("parts", []):
            if part.get("text"):
                chunks.append(part["text"])
    return "\n".join(chunks).strip() or None


def openai_synthesis(items: list[Item], start: dt.datetime, end: dt.datetime, tz: ZoneInfo) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    body = json.dumps(
        {
            "model": model,
            "input": synthesis_prompt(items, start, end, tz),
            "temperature": 0.2,
            "max_output_tokens": 3000,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return f"## 신뢰도 메모\n\nOpenAI 요약 생성에 실패했습니다: `{exc}`\n"

    if payload.get("output_text"):
        return payload["output_text"]

    chunks: list[str] = []
    for output in payload.get("output", []):
        for content in output.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                chunks.append(content["text"])
    return "\n".join(chunks).strip() or None


def fallback_synthesis(items: list[Item], tz: ZoneInfo) -> str:
    used: set[str] = set()

    def key(item: Item) -> str:
        return item.url.split("?")[0].rstrip("/")

    def take(candidates: Iterable[Item], limit: int) -> list[Item]:
        selected: list[Item] = []
        for item in candidates:
            item_key = key(item)
            if item_key in used:
                continue
            used.add(item_key)
            selected.append(item)
            if len(selected) >= limit:
                break
        return selected

    def bullet(item: Item, include_date: bool = False) -> str:
        date = item.published.astimezone(tz).strftime("%Y-%m-%d")
        detail = f" {date}." if include_date else ""
        summary = f" {item.summary}" if item.summary else ""
        return f"- [{item.title}]({item.url}) - {item.source}.{detail}{summary}"

    top_items = take(items, 5)
    ai_items = take(
        [item for item in items if any(k in item.title.lower() for k in ("ai", "llm", "openai", "anthropic", "agent", "model", "claude"))],
        4,
    )
    dev_items = take([item for item in items if item.kind in {"hn", "feed"}], 4)
    tool_items = take(
        [item for item in items if item.kind == "github" or any(k in item.title.lower() for k in ("tool", "ide", "sdk", "release", "cursor", "code"))],
        4,
    )
    quick_links = take(items, 8)

    lines = ["## 오늘의 핵심", ""]
    for item in top_items:
        lines.append(bullet(item, include_date=True))

    detail_sections = [("AI", ai_items), ("개발 이슈", dev_items), ("개발 도구", tool_items)]
    visible_sections = [(title, group) for title, group in detail_sections if group]
    if visible_sections:
        lines.extend(["", "## 자세히 보기", ""])
        for title, group in visible_sections:
            lines.extend([f"### {title}", ""])
            lines.extend(bullet(item) for item in group)
            lines.append("")

    if quick_links:
        lines.extend(["## 빠르게 열어볼 링크", ""])
        for item in quick_links:
            lines.append(f"- [{item.title}]({item.url}) - 더 살펴볼 만한 원문입니다.")

    lines.extend(
        [
            "",
            "## 신뢰도 메모",
            "",
            "- LLM 요약 없이 생성된 기본 브리프입니다. `GEMINI_API_KEY` 또는 `OPENAI_API_KEY`를 설정하면 근거 기반 한국어 요약이 생성됩니다.",
            "- 같은 링크는 섹션 간 한 번만 나오도록 정리했습니다.",
        ]
    )
    return "\n".join(lines)


def strip_footnotes(text: str) -> str:
    text = re.sub(r"\[\^\d+\]", "", text)
    text = re.sub(r"^\[\^\d+\]:.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s?\[\d+\](?=[\s.,;:]|$)", "", text)
    text = re.sub(r"^\[\d+\]:.*$", "", text, flags=re.MULTILINE)
    return text


def format_inline(text: str) -> str:
    text = strip_footnotes(text)
    pattern = re.compile(r"(\[([^\n]+?)\]\((https?://[^)\s]+)\)|\*\*([^*]+)\*\*)")
    result = []
    cursor = 0
    for match in pattern.finditer(text):
        result.append(html.escape(text[cursor : match.start()]))
        if match.group(2) and match.group(3):
            label = html.escape(match.group(2))
            url = html.escape(match.group(3), quote=True)
            result.append(f'<a href="{url}" target="_blank" rel="noreferrer">{label}</a>')
        elif match.group(4):
            result.append(f"<strong>{html.escape(match.group(4))}</strong>")
        cursor = match.end()
    result.append(html.escape(text[cursor:]))
    return "".join(result)


def close_lists(output: list[str], list_stack: list[str]) -> None:
    while list_stack:
        output.append(f"</{list_stack.pop()}>")


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    list_stack: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            close_lists(output, list_stack)
            continue

        if re.match(r"^\[\^\d+\]:", line):
            continue

        if line.startswith("### "):
            close_lists(output, list_stack)
            output.append(f"<h3>{format_inline(line[4:])}</h3>")
        elif line.startswith("## "):
            close_lists(output, list_stack)
            output.append(f"<h2>{format_inline(line[3:])}</h2>")
        elif re.match(r"^[-*]\s+", line):
            if list_stack != ["ul"]:
                close_lists(output, list_stack)
                output.append("<ul>")
                list_stack.append("ul")
            item = re.sub(r"^[-*]\s+", "", line)
            output.append(f"<li>{format_inline(item)}</li>")
        elif re.match(r"^\d+\.\s+", line):
            if list_stack != ["ol"]:
                close_lists(output, list_stack)
                output.append("<ol>")
                list_stack.append("ol")
            item = re.sub(r"^\d+\.\s+", "", line)
            output.append(f"<li>{format_inline(item)}</li>")
        else:
            close_lists(output, list_stack)
            output.append(f"<p>{format_inline(line)}</p>")
    close_lists(output, list_stack)
    return "\n".join(output)


def render_html(markdown: str, items: list[Item], start: dt.datetime, end: dt.datetime, tz: ZoneInfo) -> str:
    generated = dt.datetime.now(tz).strftime("%Y-%m-%d %H:%M")
    start_local = start.astimezone(tz)
    end_local = end.astimezone(tz)
    start_label = start_local.strftime("%m-%d %H:%M")
    end_label = end_local.strftime("%m-%d %H:%M")
    brief_date = end_local.strftime("%Y-%m-%d")
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Daily AI/Dev Brief - {brief_date}</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #17202a;
      --muted: #607080;
      --line: #d9e0e7;
      --accent: #0b6bcb;
      --accent-bg: #e8f2ff;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #101316;
        --panel: #181d22;
        --text: #edf1f5;
        --muted: #a7b2bd;
        --line: #2a333c;
        --accent: #74b7ff;
        --accent-bg: #17293a;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.65;
    }}
    main {{
      max-width: 920px;
      margin: 0 auto;
      padding: 40px 20px 64px;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      margin-bottom: 28px;
      padding-bottom: 22px;
    }}
    .badge {{
      display: inline-block;
      background: var(--accent-bg);
      color: var(--accent);
      border-radius: 999px;
      padding: 3px 10px;
      font-size: 13px;
      font-weight: 700;
      margin-bottom: 12px;
    }}
    h1 {{
      font-size: clamp(28px, 5vw, 44px);
      line-height: 1.12;
      margin: 0 0 10px;
      letter-spacing: 0;
    }}
    .meta {{
      color: var(--muted);
      display: flex;
      flex-wrap: wrap;
      gap: 8px 14px;
      font-size: 14px;
    }}
    .meta span {{
      display: inline-flex;
      align-items: center;
    }}
    article {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 28px;
    }}
    h2 {{
      border-top: 1px solid var(--line);
      font-size: 22px;
      margin: 30px 0 12px;
      padding-top: 22px;
      letter-spacing: 0;
    }}
    h2:first-child {{
      border-top: 0;
      margin-top: 0;
      padding-top: 0;
    }}
    h3 {{
      font-size: 18px;
      margin: 22px 0 8px;
      letter-spacing: 0;
    }}
    p {{ margin: 10px 0 16px; }}
    strong {{ font-weight: 750; }}
    ul {{
      padding-left: 22px;
      margin: 10px 0 18px;
    }}
    li {{ margin: 8px 0; }}
    a {{
      color: var(--accent);
      text-decoration-thickness: 1px;
      text-underline-offset: 3px;
    }}
    .sources {{
      margin-top: 28px;
      color: var(--muted);
      font-size: 13px;
    }}
    @media (max-width: 640px) {{
      main {{ padding: 24px 14px 44px; }}
      article {{ padding: 20px; }}
    }}
    @media print {{
      body {{ background: #fff; }}
      main {{ padding: 0; }}
      article {{ border: 0; padding: 0; }}
      a {{ color: #000; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="badge">Daily Brief</div>
      <h1>AI, 개발 이슈, 개발 도구 브리프</h1>
      <div class="meta">
        <span>대상: 최근 24시간</span>
        <span>기간: {start_label} - {end_label} ({tz.key})</span>
        <span>생성: {generated}</span>
        <span>수집 항목: {len(items)}개</span>
      </div>
    </header>
    <article>
      {markdown_to_html(markdown)}
    </article>
    <div class="sources">Generated by <code>weekly_brief.py</code>. Public feeds, Hacker News, and configured GitHub releases were used as evidence.</div>
  </main>
</body>
</html>
"""


def generate_brief(days: int | None = None) -> GeneratedBrief:
    days = days or int(os.getenv("BRIEF_DAYS", "1"))
    tz = ZoneInfo(os.getenv("BRIEF_TIMEZONE", "Asia/Seoul"))
    now = dt.datetime.now(tz)
    end = now.astimezone(dt.timezone.utc)
    start = (now - dt.timedelta(days=days)).astimezone(dt.timezone.utc)

    queries = csv_env("HN_QUERIES", DEFAULT_QUERIES)
    feed_urls = csv_env("FEED_URLS", DEFAULT_FEEDS)
    repos = csv_env("GITHUB_REPOS", DEFAULT_GITHUB_REPOS)
    opportunity_sources = csv_env("OPPORTUNITY_SOURCES", DEFAULT_OPPORTUNITY_SOURCES)
    opportunity_keywords = csv_env("OPPORTUNITY_KEYWORDS", DEFAULT_OPPORTUNITY_KEYWORDS)
    opportunity_type_keywords = csv_env("OPPORTUNITY_TYPE_KEYWORDS", DEFAULT_OPPORTUNITY_TYPE_KEYWORDS)
    opportunity_exclude_keywords = csv_env("OPPORTUNITY_EXCLUDE_KEYWORDS", DEFAULT_OPPORTUNITY_EXCLUDE_KEYWORDS)
    opportunity_limit = int(os.getenv("OPPORTUNITY_LIMIT", "12"))

    items = dedupe_items(
        [
            *fetch_rss_items(feed_urls, start, end),
            *fetch_hn_items(queries, start, end),
            *fetch_github_releases(repos, start, end),
        ]
    )

    synthesis = gemini_synthesis(items, start, end, tz) or openai_synthesis(items, start, end, tz) or fallback_synthesis(items, tz)
    if os.getenv("ENABLE_OPPORTUNITIES", "1") != "0":
        opportunities = fetch_opportunities(
            opportunity_sources,
            opportunity_keywords,
            opportunity_type_keywords,
            opportunity_exclude_keywords,
            opportunity_limit,
        )
        synthesis = synthesis.rstrip() + opportunities_markdown(opportunities, opportunity_limit)
    html_body = render_html(synthesis, items, start, end, tz)
    return GeneratedBrief(
        stamp=now.strftime("%Y-%m-%d"),
        timezone=tz.key,
        period_start=start.astimezone(tz).strftime("%Y-%m-%d"),
        period_end=end.astimezone(tz).strftime("%Y-%m-%d"),
        items_count=len(items),
        markdown=synthesis,
        html=html_body,
    )


def write_brief_files(brief: GeneratedBrief, output_dir: str) -> dict[str, str | int]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    markdown_path = out / f"weekly-ai-dev-brief-{brief.stamp}.md"
    html_path = out / f"weekly-ai-dev-brief-{brief.stamp}.html"
    markdown_path.write_text(brief.markdown, encoding="utf-8")
    html_path.write_text(brief.html, encoding="utf-8")
    return {
        "html": str(html_path),
        "markdown": str(markdown_path),
        "items": brief.items_count,
    }


def run() -> int:
    parser = argparse.ArgumentParser(description="Generate a daily AI/developer brief.")
    parser.add_argument("--days", type=int, default=int(os.getenv("BRIEF_DAYS", "1")))
    parser.add_argument("--output-dir", default=os.getenv("OUTPUT_DIR", "out"))
    args = parser.parse_args()

    brief = generate_brief(days=args.days)
    print(json.dumps(write_brief_files(brief, args.output_dir), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
