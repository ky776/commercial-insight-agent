#!/usr/bin/env python3
"""Read and update the public signal radar without exposing private credentials."""

from __future__ import annotations

import re
from pathlib import Path

try:
    from .social_collector import load_json, validate_public_url, write_json_atomic
except ImportError:
    from social_collector import load_json, validate_public_url, write_json_atomic


SOURCE_FIELDS = {
    "x_account": ("manual_discovery", "x_accounts"),
    "facebook_page": ("manual_discovery", "facebook_pages"),
    "github_user": ("github", "users"),
    "github_repository": ("github", "repositories"),
    "feed": (None, "feeds"),
    "public_post_url": (None, "public_post_urls"),
}


def default_social_paths(root: Path) -> tuple[Path, Path]:
    return root / "config" / "social_watchlist.json", root / "local"


def _latest_payload(local_dir: Path) -> dict:
    files = sorted((local_dir / "cache" / "social").glob("*.json"), reverse=True)
    return load_json(files[0], {}) if files else {}


def radar_status(config_path: Path, local_dir: Path) -> dict:
    config = load_json(config_path, {})
    latest = _latest_payload(local_dir)
    manual = config.get("manual_discovery", {})
    github = config.get("github", {})
    return {
        "configured": {
            "xAccounts": manual.get("x_accounts", []),
            "facebookPages": manual.get("facebook_pages", []),
            "githubUsers": github.get("users", []),
            "githubRepositories": github.get("repositories", []),
            "feeds": config.get("feeds", []),
            "publicPostUrls": config.get("public_post_urls", []),
            "dailyLimit": config.get("daily_limit", 100),
            "lookbackHours": config.get("lookback_hours", 36),
        },
        "latest": latest,
        "scheduleInstalled": (Path.home() / "Library" / "LaunchAgents" / "com.ky776.commercial-insight-social.plist").is_file(),
        "accessBoundary": "X/Facebook 账号仅作观察名单；自动采集需要公开帖子 URL、RSS 或授权 API。",
    }


def _normalize_source(source_type: str, value: str) -> str:
    value = value.strip()
    if source_type in {"x_account", "facebook_page", "github_user"}:
        value = value.lstrip("@")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", value):
            raise ValueError("账号格式不正确")
    elif source_type == "github_repository":
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
            raise ValueError("GitHub 仓库应使用 owner/repository 格式")
    elif source_type in {"feed", "public_post_url"}:
        validate_public_url(value)
    else:
        raise ValueError("不支持的来源类型")
    return value


def add_watch_source(config_path: Path, source_type: str, value: str) -> dict:
    if source_type not in SOURCE_FIELDS:
        raise ValueError("不支持的来源类型")
    normalized = _normalize_source(source_type, value)
    config = load_json(config_path, {})
    parent, field = SOURCE_FIELDS[source_type]
    container = config.setdefault(parent, {}) if parent else config
    values = container.setdefault(field, [])
    if normalized not in values:
        values.append(normalized)
        write_json_atomic(config_path, config)
    return {"sourceType": source_type, "value": normalized, "added": normalized in values}
