#!/usr/bin/env python3
"""Store, hash, parse, and cache local source materials."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO


TEXT_EXTENSIONS = {".md", ".txt", ".json", ".csv", ".yaml", ".yml"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".tiff", ".bmp"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
MAX_PREVIEW = 50_000


class MaterialError(RuntimeError):
    pass


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _safe_component(value: str, fallback: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    return clean[:100] or fallback


def _safe_filename(value: str) -> str:
    clean = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "-", Path(value).name).strip(" .")
    return clean[:180] or "material"


def _write_json_atomic(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _run(command: list[str], timeout: int = 180, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout, env={**os.environ, **(env or {})})
    except FileNotFoundError as exc:
        raise MaterialError(f"缺少本地解析工具：{command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise MaterialError(f"本地解析超时：{command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()[-800:]
        raise MaterialError(detail) from exc


def _pdf(input_path: Path, cache_dir: Path, root: Path) -> tuple[str, dict, list[str]]:
    output = cache_dir / "extracted.md"
    vault = root.parent / "commercial-insight-vault"
    result = _run([
        "/bin/sh", str(root / "scripts" / "ingest_pdf.sh"), str(input_path),
        "--vault", str(vault), "--output", str(output), "--force",
    ])
    return output.read_text(encoding="utf-8"), {"engine": "pdfplumber", "output": str(output), "command_output": result.stdout.strip()}, []


def _stored_for_api(input_path: Path) -> tuple[str, dict, list[str]]:
    return "", {"engine": "external_model_api", "source": str(input_path)}, ["原文件已本地缓存，等待选择外部模型进行理解"]


def _parse(input_path: Path, cache_dir: Path, root: Path) -> tuple[str, str, dict, list[str]]:
    extension = input_path.suffix.casefold()
    if extension in TEXT_EXTENSIONS:
        text = input_path.read_text(encoding="utf-8", errors="replace")
        output = cache_dir / "extracted.txt"
        output.write_text(text, encoding="utf-8")
        return text, "parsed", {"engine": "text", "output": str(output)}, []
    if extension == ".pdf":
        text, metadata, warnings = _pdf(input_path, cache_dir, root)
        return text, "parsed", metadata, warnings
    if extension in IMAGE_EXTENSIONS:
        text, metadata, warnings = _stored_for_api(input_path)
        return text, "stored", metadata, warnings
    if extension in AUDIO_EXTENSIONS:
        text, metadata, warnings = _stored_for_api(input_path)
        return text, "stored", metadata, warnings
    if extension in VIDEO_EXTENSIONS:
        text, metadata, warnings = _stored_for_api(input_path)
        return text, "stored", metadata, warnings
    return "", "stored", {"engine": "external_model_api"}, [f"{extension or '未知格式'} 已保存，尚未配置对应 API 能力"]


def ingest_stream(
    stream: BinaryIO,
    filename: str,
    *,
    job_id: str,
    privacy: str,
    root: Path | None = None,
) -> dict:
    root = root or project_root()
    local_dir = root / "local"
    safe_job = _safe_component(job_id, "capture")
    safe_name = _safe_filename(filename)
    input_dir = local_dir / "inputs" / safe_job
    input_dir.mkdir(parents=True, exist_ok=True)
    temporary = input_dir / f".{safe_name}.upload"
    digest = hashlib.sha256()
    size = 0
    with temporary.open("wb") as output:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
            output.write(chunk)
    content_hash = digest.hexdigest()
    input_path = input_dir / f"{content_hash[:12]}-{safe_name}"
    if input_path.exists():
        temporary.unlink()
    else:
        temporary.replace(input_path)
    cache_dir = local_dir / "cache" / "materials" / content_hash
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = cache_dir / "manifest.json"
    cached = manifest_path.is_file()
    if cached:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        extension = Path(filename).suffix.casefold()
        if extension in IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | VIDEO_EXTENSIONS and (manifest.get("metadata") or {}).get("engine") != "external_model_api":
            manifest["parse_status"] = "stored"
            manifest["metadata"] = {"engine": "external_model_api", "source": str(input_path)}
            manifest["warnings"] = ["原文件已本地缓存，等待选择外部模型进行理解"]
            manifest["error"] = None
        if privacy == "restricted" and manifest.get("sensitivity") != "restricted":
            manifest["sensitivity"] = "restricted"
        _write_json_atomic(manifest_path, manifest)
    else:
        try:
            extracted, parse_status, metadata, warnings = _parse(input_path, cache_dir, root)
            error = None
        except (OSError, ValueError, MaterialError, json.JSONDecodeError) as exc:
            extracted, parse_status, metadata, warnings, error = "", "failed", {}, [], str(exc)
        manifest = {
            "id": content_hash[:24],
            "source_file": str(input_path),
            "original_name": filename,
            "content_hash": content_hash,
            "size": size,
            "media_type": mimetypes.guess_type(filename)[0] or "application/octet-stream",
            "sensitivity": privacy,
            "parse_status": parse_status,
            "review_status": "pending",
            "metadata": metadata,
            "warnings": warnings,
            "error": error,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_json_atomic(manifest_path, manifest)
    output_path = Path((manifest.get("metadata") or {}).get("output", ""))
    extracted_text = output_path.read_text(encoding="utf-8", errors="replace")[:MAX_PREVIEW] if output_path.is_file() else ""
    return {**manifest, "cached": cached, "manifest_path": str(manifest_path), "extracted_text": extracted_text}
