#!/usr/bin/env python3
"""Build a publishable vertical video from human A-roll, captions, and Seedance B-roll."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


class VideoProductionError(RuntimeError):
    """Raised when a finished-video project cannot be prepared or rendered."""


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _safe_id(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-")
    return clean[:80] or datetime.now().strftime("video-%Y%m%d-%H%M%S")


def _run(command: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise VideoProductionError(f"缺少成片工具：{command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise VideoProductionError("成片渲染超时") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()[-1600:]
        raise VideoProductionError(f"成片渲染失败：{detail}") from exc


def _manifest(root: Path, content_hash: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{64}", content_hash):
        raise VideoProductionError("真人口播素材 ID 格式不正确")
    path = root / "local" / "cache" / "materials" / content_hash / "manifest.json"
    if not path.is_file():
        raise VideoProductionError("找不到真人口播素材")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    source = Path(manifest.get("source_file", ""))
    if not source.is_file():
        raise VideoProductionError("真人口播原文件不存在")
    if not (manifest.get("media_type", "").startswith("video/") or manifest.get("media_type", "").startswith("audio/")):
        raise VideoProductionError("成片主素材必须是视频或音频")
    return manifest


def probe_media(path: Path) -> dict:
    result = _run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], timeout=60)
    payload = json.loads(result.stdout)
    duration = float((payload.get("format") or {}).get("duration") or 0)
    if duration <= 0:
        raise VideoProductionError("无法识别真人口播时长")
    has_video = any(item.get("codec_type") == "video" for item in payload.get("streams", []))
    has_audio = any(item.get("codec_type") == "audio" for item in payload.get("streams", []))
    return {"duration": duration, "has_video": has_video, "has_audio": has_audio, "probe": payload}


def _spoken_text(script: str) -> str:
    lines = []
    for raw in script.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ">", "---", "```")):
            continue
        line = re.sub(r"^[-*+\d.、]+\s*", "", line)
        line = re.sub(r"\*\*|__|`", "", line)
        if line:
            lines.append(line)
    return "".join(lines) or script.strip()


def _wrap_caption(text: str, width: int = 15) -> list[str]:
    compact = re.sub(r"\s+", "", text)
    if len(compact) <= width:
        return [compact]
    return [compact[:width], compact[width:width * 2]]


def build_caption_cues(script: str, duration: float) -> list[dict]:
    spoken = _spoken_text(script)
    fragments = [item.strip() for item in re.split(r"(?<=[。！？!?；;])", spoken) if item.strip()]
    expanded = []
    for fragment in fragments or [spoken]:
        while len(fragment) > 30:
            expanded.append(fragment[:30])
            fragment = fragment[30:]
        if fragment:
            expanded.append(fragment)
    weights = [max(len(re.sub(r"\W", "", item)), 4) for item in expanded]
    total = sum(weights) or 1
    cursor = 0.0
    cues = []
    for index, (text, weight) in enumerate(zip(expanded, weights), 1):
        end = duration if index == len(expanded) else min(duration, cursor + duration * weight / total)
        cues.append({"index": index, "start": round(cursor, 3), "end": round(end, 3), "text": text, "lines": _wrap_caption(text)})
        cursor = end
    return cues


def _srt_time(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def write_srt(cues: list[dict], path: Path) -> None:
    blocks = []
    for cue in cues:
        blocks.append(f"{cue['index']}\n{_srt_time(cue['start'])} --> {_srt_time(cue['end'])}\n{cue['text']}")
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def _caption_runtime() -> str:
    candidates = [
        Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3",
        Path(shutil.which("python3") or ""),
    ]
    for candidate in candidates:
        if candidate.is_file():
            check = subprocess.run([str(candidate), "-c", "import PIL"], capture_output=True)
            if check.returncode == 0:
                return str(candidate)
    raise VideoProductionError("缺少字幕渲染依赖 Pillow")


def _broll_paths(root: Path, task_ids: list[str]) -> list[Path]:
    paths = []
    for task_id in task_ids[:8]:
        if not re.fullmatch(r"[A-Za-z0-9_-]{6,120}", task_id):
            raise VideoProductionError("Seedance 任务 ID 格式不正确")
        path = root / "local" / "video_outputs" / task_id / "video.mp4"
        if not path.is_file():
            raise VideoProductionError(f"Seedance 辅助镜头尚未完成：{task_id}")
        paths.append(path)
    return paths


def render_finished_video(
    content_hash: str,
    script: str,
    *,
    production_id: str,
    broll_task_ids: list[str] | None = None,
    width: int = 1080,
    height: int = 1920,
    root: Path | None = None,
) -> dict:
    root = root or project_root()
    manifest = _manifest(root, content_hash)
    source = Path(manifest["source_file"])
    media = probe_media(source)
    brolls = _broll_paths(root, broll_task_ids or [])
    if not media["has_video"] and not brolls:
        raise VideoProductionError("仅上传录音时至少需要一个已完成的 Seedance 辅助镜头")
    project_id = _safe_id(production_id)
    project_dir = root / "local" / "projects" / project_id
    export_dir = project_dir / "exports"
    caption_dir = project_dir / "subtitles" / "cards"
    export_dir.mkdir(parents=True, exist_ok=True)
    caption_dir.mkdir(parents=True, exist_ok=True)
    cues = build_caption_cues(script, media["duration"])
    srt_path = project_dir / "subtitles" / "captions.srt"
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    write_srt(cues, srt_path)
    caption_config = project_dir / "subtitles" / "caption-config.json"
    caption_config.write_text(json.dumps({
        "width": width, "height": height, "output_dir": str(caption_dir), "cues": cues,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    _run([_caption_runtime(), str(root / "scripts" / "render_caption_cards.py"), str(caption_config)], timeout=120)

    inputs = ["-i", str(source)]
    for path in brolls:
        inputs.extend(["-i", str(path)])
    caption_start = 1 + len(brolls)
    for path in sorted(caption_dir.glob("caption-*.png")):
        inputs.extend(["-loop", "1", "-i", str(path)])

    filters = []
    if media["has_video"]:
        filters.append(f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps=30,setsar=1[base0]")
    else:
        filters.append(f"color=c=#171a17:s={width}x{height}:r=30:d={media['duration']:.3f}[base0]")
    current = "base0"
    if brolls:
        usable_start = media["duration"] * 0.18
        usable_end = media["duration"] * 0.82
        slot = max((usable_end - usable_start) / len(brolls), 1.0)
        for index, _path in enumerate(brolls, 1):
            start = usable_start + (index - 1) * slot
            end = min(start + slot * 0.78, media["duration"])
            filters.append(
                f"[{index}:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
                f"trim=duration={max(end-start, 0.5):.3f},setpts=PTS-STARTPTS+{start:.3f}/TB[b{index}]"
            )
            target = f"visual{index}"
            filters.append(f"[{current}][b{index}]overlay=0:0:enable='between(t,{start:.3f},{end:.3f})'[{target}]")
            current = target
    for offset, cue in enumerate(cues):
        input_index = caption_start + offset
        target = f"captioned{offset}"
        filters.append(
            f"[{input_index}:v]format=rgba,setpts=PTS-STARTPTS[cap{offset}];"
            f"[{current}][cap{offset}]overlay=0:0:enable='between(t,{cue['start']:.3f},{cue['end']:.3f})'[{target}]"
        )
        current = target

    output = export_dir / "douyin-xiaohongshu-v001.mp4"
    command = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filters), "-map", f"[{current}]", "-map", "0:a?"]
    command.extend(["-t", f"{media['duration']:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"])
    if media["has_audio"]:
        command.extend(["-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-16:LRA=11:TP=-1.5"])
    command.extend(["-movflags", "+faststart", str(output)])
    _run(command)
    cover = export_dir / "cover.png"
    _run(["ffmpeg", "-y", "-ss", "1", "-i", str(output), "-frames:v", "1", str(cover)], timeout=120)
    project = {
        "id": project_id,
        "status": "rendered",
        "source_content_hash": content_hash,
        "source_file": str(source),
        "script": script,
        "duration": media["duration"],
        "broll_task_ids": broll_task_ids or [],
        "captions": str(srt_path),
        "output_path": str(output),
        "cover_path": str(cover),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (project_dir / "project.json").write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
    return project


def get_finished_video(production_id: str, root: Path | None = None) -> Path:
    root = root or project_root()
    path = root / "local" / "projects" / _safe_id(production_id) / "exports" / "douyin-xiaohongshu-v001.mp4"
    if not path.is_file():
        raise VideoProductionError("成片尚未生成")
    return path
