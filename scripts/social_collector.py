#!/usr/bin/env python3
"""Collect, score, deduplicate, and store public social and GitHub signals."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import ipaddress
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import asdict, dataclass
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


USER_AGENT = "commercial-insight-agent/0.1 (+local research; public sources only)"
GITHUB_ACCEPT = "application/vnd.github+json"
GITHUB_API_VERSION = "2022-11-28"
MAX_EXCERPT = 500


class CollectionError(RuntimeError):
    pass


@dataclass
class Signal:
    id: str
    platform: str
    source_type: str
    author: str
    company: str
    title: str
    source_url: str
    published_at: str
    collected_at: str
    categories: list[str]
    summary: str
    raw_excerpt: str
    relevance_score: int = 0
    heat_score: int = 0
    credibility_score: int = 0
    recency_score: int = 0
    business_value_score: int = 0
    novelty_score: int = 100
    company_activity_count: int = 1
    evidence_status: str = "needs_verification"
    worth_following: str = "low"
    content_angles: list[str] | None = None
    requires_verification: list[str] | None = None


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_datetime(value: dt.datetime | None) -> str:
    target = value or utc_now()
    if target.tzinfo is None:
        target = target.replace(tzinfo=dt.timezone.utc)
    return target.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_datetime(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    clean = value.strip()
    try:
        if clean.endswith("Z"):
            parsed = dt.datetime.fromisoformat(clean[:-1] + "+00:00")
        else:
            parsed = dt.datetime.fromisoformat(clean)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(clean)
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def compact_text(value: str | None, limit: int = MAX_EXCERPT) -> str:
    clean = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:limit]


def stable_id(platform: str, external_id: str, url: str) -> str:
    material = f"{platform}|{external_id}|{url}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:24]


class HttpClient:
    def __init__(self, cache_dir: Path, timeout: int = 20):
        self.cache_dir = cache_dir
        self.timeout = timeout
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()}.json"

    def get(self, url: str, headers: dict[str, str] | None = None) -> tuple[bytes, dict[str, str]]:
        validate_public_url(url)
        cache_path = self._cache_path(url)
        cached = {}
        if cache_path.exists():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                cached = {}
        request_headers = {"User-Agent": USER_AGENT, "Accept": "*/*", **(headers or {})}
        if cached.get("etag"):
            request_headers["If-None-Match"] = cached["etag"]
        request = urllib.request.Request(url, headers=request_headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read()
                response_headers = {key.lower(): value for key, value in response.headers.items()}
                payload = {
                    "etag": response_headers.get("etag"),
                    "body": body.decode("utf-8", errors="replace"),
                    "fetched_at": iso_datetime(utc_now()),
                }
                cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                return body, response_headers
        except urllib.error.HTTPError as exc:
            if exc.code == 304 and cached.get("body") is not None:
                return cached["body"].encode("utf-8"), {"etag": cached.get("etag", "")}
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            detail = f"HTTP {exc.code}"
            if retry_after:
                detail += f", retry after {retry_after}s"
            raise CollectionError(f"{url}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise CollectionError(f"{url}: {exc.reason}") from exc

    def get_json(self, url: str, headers: dict[str, str] | None = None) -> Any:
        body, _ = self.get(url, headers)
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise CollectionError(f"{url}: invalid JSON") from exc


def validate_public_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise CollectionError(f"Blocked non-public URL: {url}")
    hostname = parsed.hostname.casefold()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise CollectionError(f"Blocked local URL: {url}")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return
    if not address.is_global:
        raise CollectionError(f"Blocked private or local URL: {url}")


def github_headers() -> dict[str, str]:
    headers = {"Accept": GITHUB_ACCEPT, "X-GitHub-Api-Version": GITHUB_API_VERSION}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def github_event_title(event: dict) -> str:
    event_type = event.get("type", "GitHubEvent")
    repo = event.get("repo", {}).get("name", "unknown repository")
    payload = event.get("payload") or {}
    action = payload.get("action") or payload.get("ref_type") or "activity"
    if event_type == "PushEvent":
        messages = [compact_text(item.get("message"), 100) for item in payload.get("commits", [])[:2]]
        return f"{repo}: {'; '.join(messages) or 'new commits'}"
    if event_type == "ReleaseEvent":
        release = payload.get("release") or {}
        return f"{repo} released {release.get('name') or release.get('tag_name') or 'a new version'}"
    return f"{repo}: {event_type.replace('Event', '')} {action}"


def github_event_url(event: dict) -> str:
    payload = event.get("payload") or {}
    for key in ("release", "pull_request", "issue"):
        value = payload.get(key) or {}
        if value.get("html_url"):
            return value["html_url"]
    repo = event.get("repo", {}).get("name", "")
    return f"https://github.com/{repo}" if repo else "https://github.com/"


def collect_github_user(client: HttpClient, username: str, since: dt.datetime) -> list[Signal]:
    url = f"https://api.github.com/users/{urllib.parse.quote(username)}/events/public?per_page=30"
    events = client.get_json(url, github_headers())
    signals = []
    for event in events if isinstance(events, list) else []:
        published = parse_datetime(event.get("created_at"))
        if published and published < since:
            continue
        title = github_event_title(event)
        source_url = github_event_url(event)
        signals.append(Signal(
            id=stable_id("github", str(event.get("id", "")), source_url),
            platform="github",
            source_type="github_event",
            author=event.get("actor", {}).get("display_login") or username,
            company=event.get("repo", {}).get("name", "").split("/")[0],
            title=title,
            source_url=source_url,
            published_at=iso_datetime(published) if published else "",
            collected_at=iso_datetime(utc_now()),
            categories=[],
            summary=title,
            raw_excerpt=title,
            evidence_status="public_primary",
        ))
    return signals


def collect_github_repository_events(client: HttpClient, repository: str, since: dt.datetime) -> list[Signal]:
    encoded = "/".join(urllib.parse.quote(part) for part in repository.split("/", 1))
    url = f"https://api.github.com/repos/{encoded}/events?per_page=30"
    events = client.get_json(url, github_headers())
    signals = []
    for event in events if isinstance(events, list) else []:
        published = parse_datetime(event.get("created_at"))
        if published and published < since:
            continue
        title = github_event_title(event)
        source_url = github_event_url(event)
        signals.append(Signal(
            id=stable_id("github", str(event.get("id", "")), source_url),
            platform="github",
            source_type="github_event",
            author=event.get("actor", {}).get("display_login") or event.get("actor", {}).get("login", ""),
            company=repository.split("/")[0],
            title=title,
            source_url=source_url,
            published_at=iso_datetime(published) if published else "",
            collected_at=iso_datetime(utc_now()),
            categories=[],
            summary=title,
            raw_excerpt=title,
            evidence_status="public_primary",
        ))
    return signals


def collect_github_releases(client: HttpClient, repository: str, since: dt.datetime) -> list[Signal]:
    encoded = "/".join(urllib.parse.quote(part) for part in repository.split("/", 1))
    url = f"https://api.github.com/repos/{encoded}/releases?per_page=10"
    releases = client.get_json(url, github_headers())
    signals = []
    for release in releases if isinstance(releases, list) else []:
        published = parse_datetime(release.get("published_at") or release.get("created_at"))
        if published and published < since:
            continue
        name = release.get("name") or release.get("tag_name") or "new release"
        body = compact_text(release.get("body"))
        source_url = release.get("html_url") or f"https://github.com/{repository}/releases"
        signals.append(Signal(
            id=stable_id("github", str(release.get("id", "")), source_url),
            platform="github",
            source_type="github_release",
            author=release.get("author", {}).get("login", repository.split("/")[0]),
            company=repository.split("/")[0],
            title=f"{repository} released {name}",
            source_url=source_url,
            published_at=iso_datetime(published) if published else "",
            collected_at=iso_datetime(utc_now()),
            categories=[],
            summary=body or f"New release from {repository}",
            raw_excerpt=body,
            evidence_status="public_primary",
        ))
    return signals


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def child_text(element: ET.Element, names: tuple[str, ...]) -> str:
    for child in element.iter():
        if local_name(child.tag) in names and child.text:
            return child.text.strip()
    return ""


def feed_link(element: ET.Element) -> str:
    for child in element.iter():
        if local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href")
        if href and child.attrib.get("rel", "alternate") in {"alternate", ""}:
            return href
        if child.text and child.text.strip().startswith("http"):
            return child.text.strip()
    return ""


def parse_feed(payload: bytes, feed_url: str, since: dt.datetime) -> list[Signal]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise CollectionError(f"{feed_url}: invalid RSS/Atom") from exc
    entries = [item for item in root.iter() if local_name(item.tag) in {"item", "entry"}]
    signals = []
    for entry in entries:
        title = compact_text(child_text(entry, ("title",)), 220)
        source_url = feed_link(entry) or feed_url
        published_text = child_text(entry, ("published", "updated", "pubdate", "date"))
        published = parse_datetime(published_text)
        if published and published < since:
            continue
        author = child_text(entry, ("author", "creator", "name"))
        description = child_text(entry, ("summary", "description", "content", "encoded"))
        external_id = child_text(entry, ("guid", "id")) or source_url
        signals.append(Signal(
            id=stable_id("rss", external_id, source_url),
            platform="rss",
            source_type="rss_entry",
            author=compact_text(author, 100),
            company=urllib.parse.urlparse(feed_url).netloc,
            title=title or source_url,
            source_url=source_url,
            published_at=iso_datetime(published) if published else "",
            collected_at=iso_datetime(utc_now()),
            categories=[],
            summary=compact_text(description),
            raw_excerpt=compact_text(description),
            evidence_status="public_secondary",
        ))
    return signals


class OpenGraphParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values: dict[str, str] = {}
        self.title_parts: list[str] = []
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag.lower() == "title":
            self.in_title = True
        if tag.lower() != "meta":
            return
        key = attributes.get("property") or attributes.get("name")
        value = attributes.get("content")
        if key and value:
            self.values[key.lower()] = value

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)


def collect_public_post(client: HttpClient, url: str) -> Signal | None:
    body, _ = client.get(url, {"Accept": "text/html,application/xhtml+xml"})
    parser = OpenGraphParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    title = compact_text(parser.values.get("og:title") or "".join(parser.title_parts), 220)
    description = compact_text(parser.values.get("og:description") or parser.values.get("description"))
    if not title or not description:
        return None
    host = urllib.parse.urlparse(url).netloc.lower()
    platform = "x" if host in {"x.com", "twitter.com", "www.x.com", "www.twitter.com"} else "facebook" if "facebook.com" in host else "public_web"
    published = parse_datetime(parser.values.get("article:published_time"))
    author = compact_text(parser.values.get("author") or parser.values.get("og:site_name"), 100)
    return Signal(
        id=stable_id(platform, url, url),
        platform=platform,
        source_type="public_post",
        author=author,
        company=author,
        title=title,
        source_url=url,
        published_at=iso_datetime(published) if published else "",
        collected_at=iso_datetime(utc_now()),
        categories=[],
        summary=description,
        raw_excerpt=description,
        evidence_status="public_primary" if platform in {"x", "facebook"} else "public_secondary",
    )


def classify(signal: Signal, topics: dict[str, list[str]]) -> list[str]:
    haystack = f"{signal.title} {signal.summary} {signal.raw_excerpt}".casefold()
    categories = []
    for category, keywords in topics.items():
        if any(keyword.casefold() in haystack for keyword in keywords):
            categories.append(category)
    return categories


def content_angles(categories: list[str]) -> list[str]:
    angles = {
        "model_release": "新模型改变了哪类内容或营销任务的成本边界？",
        "agent_ecosystem": "Agent 从演示走向业务流程还缺哪些条件？",
        "ai_industry_change": "这项行业变化对中小品牌意味着什么？",
        "business_model": "产品能力之外，定价和变现路径是否成立？",
        "funding_and_ipo": "资本动作反映了哪种商业预期？",
        "company_heat": "热度来自真实采用、产品发布还是市场叙事？",
        "opinion_and_debate": "该观点成立的前提和反例是什么？",
    }
    return [angles[category] for category in categories if category in angles][:3]


def score_signal(signal: Signal, topics: dict[str, list[str]], now: dt.datetime) -> Signal:
    signal.categories = classify(signal, topics)
    matched_keywords = 0
    haystack = f"{signal.title} {signal.summary}".casefold()
    for category in signal.categories:
        matched_keywords += sum(1 for keyword in topics.get(category, []) if keyword.casefold() in haystack)
    signal.relevance_score = min(100, len(signal.categories) * 18 + matched_keywords * 6)
    signal.heat_score = {
        "github_release": 78,
        "github_event": 46,
        "public_post": 55,
        "rss_entry": 52,
    }.get(signal.source_type, 40)
    signal.credibility_score = 90 if signal.evidence_status == "public_primary" else 68
    published = parse_datetime(signal.published_at)
    age_hours = max((now - published.astimezone(dt.timezone.utc)).total_seconds() / 3600, 0) if published else 36
    signal.recency_score = 100 if age_hours <= 12 else 82 if age_hours <= 24 else 60 if age_hours <= 72 else 25
    update_value_score(signal)
    signal.content_angles = content_angles(signal.categories)
    signal.requires_verification = [
        "回看原始链接确认上下文",
        "涉及融资、估值、性能或收入数字时寻找第二来源",
    ]
    return signal


def update_value_score(signal: Signal) -> None:
    value = (
        signal.relevance_score * 0.45
        + signal.heat_score * 0.20
        + signal.credibility_score * 0.20
        + signal.recency_score * 0.15
    )
    signal.business_value_score = round(value)
    signal.worth_following = "high" if value >= 72 else "medium" if value >= 52 else "low"


def apply_company_heat(signals: list[Signal]) -> None:
    counts = Counter(signal.company for signal in signals if signal.company)
    for signal in signals:
        signal.company_activity_count = counts.get(signal.company, 1)
        signal.heat_score = min(100, signal.heat_score + min(max(signal.company_activity_count - 1, 0) * 4, 20))
        update_value_score(signal)


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def merge_signals(existing: list[dict], incoming: list[Signal]) -> list[Signal]:
    merged: dict[str, Signal] = {}
    for item in existing:
        try:
            signal = Signal(**item)
            merged[signal.id] = signal
        except TypeError:
            continue
    for signal in incoming:
        merged[signal.id] = signal
    return list(merged.values())


def deduplicate_by_url(signals: list[Signal]) -> list[Signal]:
    selected: dict[str, Signal] = {}
    for signal in signals:
        key = signal.source_url.rstrip("/").casefold() or signal.id
        current = selected.get(key)
        if current is None or signal.business_value_score > current.business_value_score:
            selected[key] = signal
    return list(selected.values())


def markdown_escape(value: str) -> str:
    return value.replace("\n", " ").replace("|", "\\|").strip()


def render_daily_note(date: str, signals: list[Signal], errors: list[str], collected_at: str) -> str:
    platforms = sorted({signal.platform for signal in signals})
    categories = sorted({category for signal in signals for category in signal.categories})
    lines = [
        "---",
        "type: source",
        "status: inbox",
        "source_type: social_daily_signals",
        f"published_at: {date}",
        f"collected_at: {collected_at}",
        f"item_count: {len(signals)}",
        f"platforms: [{', '.join(platforms)}]",
        f"topics: [{', '.join(categories)}]",
        "tags: [每日信号, 社交动态, AI行业]",
        "confidence: medium",
        "---",
        "",
        f"# {date} AI 与商业动态信号",
        "",
        "> 仅收录公开可访问来源。自动评分用于排序，不代表事实已经核验。发布前必须回看原始链接。",
        "",
        "## 今日概览",
        "",
        f"- 有效信号：{len(signals)}",
        f"- 涉及平台：{', '.join(platforms) or '无'}",
        f"- 主题：{', '.join(categories) or '无'}",
        f"- 采集异常：{len(errors)}",
        "",
        "## 信号列表",
        "",
    ]
    for index, signal in enumerate(signals, 1):
        lines.extend([
            f"### {index}. {markdown_escape(signal.title)}",
            "",
            f"- ID：`{signal.id}`",
            f"- 平台：{signal.platform}",
            f"- 类型：{signal.source_type}",
            f"- 作者/账号：{markdown_escape(signal.author) or '未识别'}",
            f"- 公司/项目：{markdown_escape(signal.company) or '未识别'}",
            f"- 发布时间：{signal.published_at}",
            f"- 分类：{', '.join(signal.categories) or '待分类'}",
            f"- 热度分：{signal.heat_score}",
            f"- 相关分：{signal.relevance_score}",
            f"- 可信度分：{signal.credibility_score}",
            f"- 商业价值分：{signal.business_value_score}",
            f"- 新颖度分：{signal.novelty_score}",
            f"- 当日公司活动数：{signal.company_activity_count}",
            f"- 是否跟进：{signal.worth_following}",
            f"- 证据状态：{signal.evidence_status}",
            f"- 原始链接：{signal.source_url}",
            "",
            f"**摘要**：{markdown_escape(signal.summary) or '无摘要'}",
            "",
            "**可转化角度**：",
            "",
        ])
        lines.extend(f"- {angle}" for angle in (signal.content_angles or ["待人工判断"]))
        lines.extend(["", "**核验要求**：", ""])
        lines.extend(f"- {item}" for item in (signal.requires_verification or []))
        lines.append("")
    if errors:
        lines.extend(["## 采集异常", ""])
        lines.extend(f"- {markdown_escape(error)}" for error in errors)
        lines.append("")
    return "\n".join(lines)


def collect(config_path: Path, vault: Path, local_dir: Path, dry_run: bool = False) -> dict:
    config = load_json(config_path, None)
    if not isinstance(config, dict):
        raise CollectionError(f"Invalid config: {config_path}")
    now = utc_now()
    since = now - dt.timedelta(hours=int(config.get("lookback_hours", 36)))
    today = now.astimezone().date().isoformat()
    client = HttpClient(local_dir / "cache" / "http")
    errors: list[str] = []
    incoming: list[Signal] = []

    for username in config.get("github", {}).get("users", []):
        try:
            incoming.extend(collect_github_user(client, username, since))
        except CollectionError as exc:
            errors.append(str(exc))
    for repository in config.get("github", {}).get("repositories", []):
        try:
            incoming.extend(collect_github_releases(client, repository, since))
        except CollectionError as exc:
            errors.append(str(exc))
        if config.get("github", {}).get("include_repository_events", True):
            try:
                incoming.extend(collect_github_repository_events(client, repository, since))
            except CollectionError as exc:
                errors.append(str(exc))
    for feed_url in config.get("feeds", []):
        try:
            payload, _ = client.get(feed_url, {"Accept": "application/atom+xml,application/rss+xml,application/xml,text/xml"})
            incoming.extend(parse_feed(payload, feed_url, since))
        except CollectionError as exc:
            errors.append(str(exc))
    for post_url in config.get("public_post_urls", []):
        try:
            signal = collect_public_post(client, post_url)
            if signal:
                incoming.append(signal)
            else:
                errors.append(f"{post_url}: no public post metadata found")
        except CollectionError as exc:
            errors.append(str(exc))

    topics = config.get("topics", {})
    scored = [score_signal(signal, topics, now) for signal in incoming]
    apply_company_heat(scored)
    minimum = int(config.get("minimum_value_score", 42))
    scored = [signal for signal in scored if signal.categories and signal.business_value_score >= minimum]
    raw_path = local_dir / "cache" / "social" / f"{today}.json"
    existing = load_json(raw_path, {}).get("signals", []) if raw_path.exists() else []
    state_path = local_dir / "social_state.json"
    state = load_json(state_path, {"seen": {}})
    seen = state.get("seen", {}) if isinstance(state, dict) else {}
    fresh = []
    for signal in scored:
        last_seen = seen.get(signal.id)
        if last_seen and last_seen != today:
            continue
        signal.novelty_score = 100 if not last_seen else 60
        fresh.append(signal)
    merged = deduplicate_by_url(merge_signals(existing, fresh))
    merged.sort(key=lambda item: (-item.business_value_score, item.published_at, item.id))
    selected = merged[: max(1, min(int(config.get("daily_limit", 100)), 100))]
    collected_at = iso_datetime(now)
    payload = {
        "date": today,
        "collected_at": collected_at,
        "signal_count": len(selected),
        "errors": errors,
        "signals": [asdict(signal) for signal in selected],
    }
    note_path = vault / "10_Sources" / "Social" / f"{today}-social-signals.md"
    if not dry_run:
        write_json_atomic(raw_path, payload)
        note_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = note_path.with_suffix(note_path.suffix + ".tmp")
        temporary.write_text(render_daily_note(today, selected, errors, collected_at), encoding="utf-8")
        temporary.replace(note_path)
        cutoff = (now.date() - dt.timedelta(days=45)).isoformat()
        retained_seen = {key: value for key, value in seen.items() if isinstance(value, str) and value >= cutoff}
        retained_seen.update({signal.id: today for signal in selected})
        write_json_atomic(state_path, {"updated_at": collected_at, "seen": retained_seen})
    return {
        "date": today,
        "signals": len(selected),
        "errors": errors,
        "note": str(note_path),
        "raw": str(raw_path),
        "dry_run": dry_run,
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=root / "config" / "social_watchlist.json")
    parser.add_argument("--vault", type=Path, default=root.parent / "commercial-insight-vault")
    parser.add_argument("--local-dir", type=Path, default=root / "local")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        report = collect(
            args.config.expanduser().resolve(),
            args.vault.expanduser().resolve(),
            args.local_dir.expanduser().resolve(),
            args.dry_run,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (OSError, CollectionError, ValueError) as exc:
        print(f"Social collection failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
