#!/usr/bin/env python3
"""Create, track, and locally cache Seedance video-generation jobs."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

try:
    from .model_providers import load_provider_config
except ImportError:
    from model_providers import load_provider_config


class VideoGenerationError(RuntimeError):
    """Raised when a video job cannot be created, queried, or downloaded."""


VALID_RATIOS = {"16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "adaptive"}
VALID_DURATIONS = {5, 10, 15}
VALID_RESOLUTIONS = {"480p", "720p", "1080p"}
MAX_VIDEO_BYTES = 250_000_000


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _request_json(request: urllib.request.Request, transport: Callable | None = None) -> dict:
    opener = transport or urllib.request.urlopen
    try:
        with opener(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        raise VideoGenerationError(f"Seedance API 请求失败（HTTP {exc.code}）：{detail}") from exc
    except (OSError, ValueError) as exc:
        raise VideoGenerationError(f"Seedance API 请求失败：{exc}") from exc


def _provider(root: Path) -> tuple[dict, str, str]:
    item = load_provider_config(root)["providers"]["seedance"]
    api_key = os.environ.get(item["api_key_env"], "")
    if not api_key:
        raise VideoGenerationError(f"未配置 {item['api_key_env']}")
    model = os.environ.get("SEEDANCE_VIDEO_GENERATION_MODEL") or item["models"]["video_generation"]
    return item, api_key, model


def _job_path(root: Path, task_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,120}", task_id):
        raise VideoGenerationError("Seedance 任务 ID 格式不正确")
    return root / "local" / "video_jobs" / task_id / "job.json"


def _write_job(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def create_seedance_job(
    prompt: str,
    *,
    ratio: str = "9:16",
    duration: int = 5,
    resolution: str = "720p",
    reference_urls: list[str] | None = None,
    confirmed_cost: bool = False,
    root: Path | None = None,
    transport: Callable | None = None,
) -> dict:
    root = root or project_root()
    if not confirmed_cost:
        raise VideoGenerationError("提交视频生成前必须确认可能产生模型费用")
    prompt = prompt.strip()
    if not prompt:
        raise VideoGenerationError("视频生成提示词不能为空")
    if ratio not in VALID_RATIOS or duration not in VALID_DURATIONS or resolution not in VALID_RESOLUTIONS:
        raise VideoGenerationError("视频比例、时长或分辨率不受支持")
    item, api_key, model = _provider(root)
    content = [{"type": "text", "text": f"{prompt} --ratio {ratio} --dur {duration} --resolution {resolution}"}]
    for url in (reference_urls or [])[:4]:
        parsed = urlparse(url)
        if parsed.scheme not in {"https", "asset"}:
            raise VideoGenerationError("参考素材仅支持 HTTPS 或 asset:// 地址")
        content.append({"type": "image_url", "image_url": {"url": url}})
    request = urllib.request.Request(
        item["base_url"],
        data=json.dumps({"model": model, "content": content, "return_last_frame": False}, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    response = _request_json(request, transport)
    task_id = str(response.get("id", ""))
    if not task_id:
        raise VideoGenerationError("Seedance API 没有返回任务 ID")
    job = {
        "id": task_id,
        "provider": "seedance",
        "model": model,
        "prompt": prompt,
        "ratio": ratio,
        "duration": duration,
        "resolution": resolution,
        "reference_urls": reference_urls or [],
        "status": "queued",
        "remote": response,
        "video_url": None,
        "output_path": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_job(_job_path(root, task_id), job)
    return job


def _download_video(url: str, destination: Path, downloader: Callable | None = None) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise VideoGenerationError("Seedance 返回了不安全的视频地址")
    opener = downloader or urllib.request.urlopen
    request = urllib.request.Request(url, headers={"User-Agent": "CommercialInsightAgent/0.1"})
    try:
        with opener(request, timeout=180) as response:
            length = int(response.headers.get("Content-Length", "0") or 0)
            if length > MAX_VIDEO_BYTES:
                raise VideoGenerationError("生成视频超过本地下载上限")
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(".mp4.tmp")
            total = 0
            with temporary.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_VIDEO_BYTES:
                        raise VideoGenerationError("生成视频超过本地下载上限")
                    output.write(chunk)
            temporary.replace(destination)
    except OSError as exc:
        raise VideoGenerationError(f"生成视频下载失败：{exc}") from exc


def refresh_seedance_job(
    task_id: str,
    *,
    root: Path | None = None,
    transport: Callable | None = None,
    downloader: Callable | None = None,
) -> dict:
    root = root or project_root()
    path = _job_path(root, task_id)
    if not path.is_file():
        raise VideoGenerationError("本地没有这个 Seedance 任务")
    job = json.loads(path.read_text(encoding="utf-8"))
    item, api_key, _model = _provider(root)
    request = urllib.request.Request(
        f"{item['base_url'].rstrip('/')}/{task_id}",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="GET",
    )
    response = _request_json(request, transport)
    job["status"] = response.get("status", job.get("status"))
    job["remote"] = response
    job["updated_at"] = datetime.now(timezone.utc).isoformat()
    video_url = (response.get("content") or {}).get("video_url")
    if job["status"] == "succeeded" and video_url:
        destination = root / "local" / "video_outputs" / task_id / "video.mp4"
        if not destination.is_file():
            _download_video(video_url, destination, downloader)
        job["video_url"] = video_url
        job["output_path"] = str(destination)
    _write_job(path, job)
    return job


def get_video_path(task_id: str, root: Path | None = None) -> Path:
    root = root or project_root()
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,120}", task_id):
        raise VideoGenerationError("Seedance 任务 ID 格式不正确")
    path = root / "local" / "video_outputs" / task_id / "video.mp4"
    if not path.is_file():
        raise VideoGenerationError("本地视频尚未生成或下载")
    return path
