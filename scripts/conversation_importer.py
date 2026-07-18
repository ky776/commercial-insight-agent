#!/usr/bin/env python3
"""Import ChatGPT/Codex conversation exports into a local review queue."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ROLE_ALIASES = {
    "user": "user",
    "human": "user",
    "用户": "user",
    "assistant": "assistant",
    "助手": "assistant",
    "chatgpt": "assistant",
    "codex": "assistant",
    "system": "system",
    "系统": "system",
}
CLASS_KEYWORDS = {
    "strategy": ("战略", "创业", "商业模式", "定位", "投资", "roadmap", "路径"),
    "product": ("产品", "用户流程", "需求", "prd", "前端", "功能"),
    "engineering": ("代码", "开发", "接口", "数据库", "python", "javascript", "架构"),
    "configuration": ("配置", "变量", "环境变量", "token", "api key", "ssh"),
    "operations": ("部署", "启动", "运行", "报错", "github", "git", "obsidian"),
    "content": ("自媒体", "公众号", "短视频", "脚本", "选题", "内容"),
    "customer": ("客户", "showcase", "咨询", "诊断", "交付"),
    "finance": ("融资", "预算", "收入", "成本", "估值", "上市"),
    "career": ("职业", "工作", "辞职", "经历", "简历"),
}
TOPIC_KEYWORDS = {
    "Codex": ("codex",),
    "ChatGPT": ("chatgpt",),
    "Obsidian": ("obsidian", "知识库"),
    "GitHub": ("github", "git"),
    "Agent": ("agent", "智能体"),
    "广告商业化": ("广告", "商业化", "变现"),
    "自媒体": ("自媒体", "公众号", "短视频"),
    "创业": ("创业", "客户", "融资"),
}
SENSITIVE_PATTERNS = (
    re.compile(r"\b(?:sk|ghp|github_pat)_[A-Za-z0-9_-]{12,}\b", re.I),
    re.compile(r"(?:password|密码|secret|token)\s*[:=]\s*\S+", re.I),
)


@dataclass
class Turn:
    id: str
    role: str
    content: str
    created_at: str | None = None


@dataclass
class Conversation:
    id: str
    title: str
    created_at: str | None
    turns: list[Turn]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(clean_text(item) for item in value if clean_text(item)).strip()
    if isinstance(value, dict):
        if "parts" in value:
            return clean_text(value["parts"])
        if "text" in value:
            return clean_text(value["text"])
    return ""


def iso_time(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return dt.datetime.fromtimestamp(value, tz=dt.timezone.utc).isoformat()
    text = str(value).strip()
    return text or None


def chatgpt_turn(node: dict) -> Turn | None:
    message = node.get("message") or {}
    role = ((message.get("author") or {}).get("role") or "").casefold()
    content = clean_text(message.get("content") or message.get("text"))
    if role not in ROLE_ALIASES or not content:
        return None
    return Turn(
        id=str(message.get("id") or node.get("id") or ""),
        role=ROLE_ALIASES[role],
        content=content,
        created_at=iso_time(message.get("create_time")),
    )


def chatgpt_conversation(item: dict, ordinal: int) -> Conversation:
    mapping = item.get("mapping") or {}
    ordered_nodes: list[dict] = []
    current = item.get("current_node")
    visited = set()
    while current and current not in visited and current in mapping:
        visited.add(current)
        node = mapping[current]
        ordered_nodes.append(node)
        current = node.get("parent")
    if ordered_nodes:
        ordered_nodes.reverse()
    else:
        ordered_nodes = sorted(
            mapping.values(),
            key=lambda node: ((node.get("message") or {}).get("create_time") or 0, str(node.get("id", ""))),
        )
    turns = [turn for node in ordered_nodes if (turn := chatgpt_turn(node))]
    conversation_id = str(item.get("conversation_id") or item.get("id") or f"chatgpt-{ordinal}")
    return Conversation(
        id=conversation_id,
        title=clean_text(item.get("title")) or f"ChatGPT conversation {ordinal}",
        created_at=iso_time(item.get("create_time") or (turns[0].created_at if turns else None)),
        turns=turns,
    )


def generic_turn(item: dict, ordinal: int) -> Turn | None:
    role = str(item.get("role") or item.get("author") or item.get("speaker") or "").casefold()
    content = clean_text(item.get("content") or item.get("text") or item.get("message"))
    if role not in ROLE_ALIASES or not content:
        return None
    return Turn(
        id=str(item.get("id") or f"turn-{ordinal}"),
        role=ROLE_ALIASES[role],
        content=content,
        created_at=iso_time(item.get("created_at") or item.get("create_time") or item.get("timestamp")),
    )


def generic_conversations(payload: Any, source_stem: str) -> list[Conversation]:
    if isinstance(payload, dict) and "mapping" in payload:
        return [chatgpt_conversation(payload, 1)]
    items = payload if isinstance(payload, list) else payload.get("conversations", []) if isinstance(payload, dict) else []
    if items and all(isinstance(item, dict) and ("role" in item or "speaker" in item) for item in items):
        turns = [turn for index, item in enumerate(items, 1) if (turn := generic_turn(item, index))]
        return [Conversation(source_stem, source_stem, turns[0].created_at if turns else None, turns)]
    conversations = []
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            continue
        if "mapping" in item:
            conversations.append(chatgpt_conversation(item, index))
            continue
        raw_turns = item.get("messages") or item.get("turns") or []
        turns = [turn for turn_index, raw in enumerate(raw_turns, 1) if isinstance(raw, dict) and (turn := generic_turn(raw, turn_index))]
        conversations.append(Conversation(
            id=str(item.get("id") or item.get("conversation_id") or f"{source_stem}-{index}"),
            title=clean_text(item.get("title")) or f"{source_stem} {index}",
            created_at=iso_time(item.get("created_at") or item.get("create_time")),
            turns=turns,
        ))
    return conversations


MARKDOWN_ROLE_RE = re.compile(r"^#{1,4}\s*(User|Human|用户|Assistant|ChatGPT|Codex|助手)\s*$", re.I | re.M)


def markdown_conversation(text: str, source_stem: str) -> list[Conversation]:
    matches = list(MARKDOWN_ROLE_RE.finditer(text))
    turns = []
    for index, match in enumerate(matches, 1):
        end = matches[index].start() if index < len(matches) else len(text)
        role = ROLE_ALIASES[match.group(1).casefold()]
        content = text[match.end():end].strip()
        if content:
            turns.append(Turn(f"turn-{index}", role, content))
    if not turns and text.strip():
        turns = [Turn("turn-1", "user", text.strip())]
    return [Conversation(source_stem, source_stem, None, turns)]


def read_export(path: Path) -> tuple[str, list[Conversation]]:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            candidates = [name for name in archive.namelist() if name.endswith("conversations.json")]
            if not candidates:
                raise ValueError("ZIP 中没有找到 conversations.json")
            payload = json.loads(archive.read(candidates[0]).decode("utf-8"))
        return "chatgpt", generic_conversations(payload, path.stem)
    if path.suffix.lower() in {".md", ".txt"}:
        return "codex", markdown_conversation(path.read_text(encoding="utf-8"), path.stem)
    if path.suffix.lower() == ".jsonl":
        payload = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return "codex", generic_conversations(payload, path.stem)
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        platform = "chatgpt" if isinstance(payload, list) and any(isinstance(item, dict) and "mapping" in item for item in payload) else "codex"
        return platform, generic_conversations(payload, path.stem)
    raise ValueError("仅支持 ZIP、JSON、JSONL、Markdown 和 TXT")


def classify_question(text: str) -> str:
    haystack = text.casefold()
    scores = {name: sum(1 for keyword in keywords if keyword.casefold() in haystack) for name, keywords in CLASS_KEYWORDS.items()}
    name, score = max(scores.items(), key=lambda item: item[1])
    return name if score else "unresolved"


def topics_for(text: str) -> list[str]:
    haystack = text.casefold()
    return [topic for topic, keywords in TOPIC_KEYWORDS.items() if any(keyword.casefold() in haystack for keyword in keywords)]


def contains_sensitive_value(text: str) -> bool:
    return any(pattern.search(text) for pattern in SENSITIVE_PATTERNS)


def redact(text: str) -> str:
    value = text
    for pattern in SENSITIVE_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


def question_records(conversation: Conversation, platform: str, source_hash: str, project: str | None, sensitivity: str) -> list[dict]:
    records = []
    for index, turn in enumerate(conversation.turns):
        if turn.role != "user":
            continue
        answer = next((item for item in conversation.turns[index + 1:] if item.role == "assistant"), None)
        combined = f"{turn.content}\n{answer.content if answer else ''}"
        record_sensitivity = "restricted" if sensitivity == "restricted" or contains_sensitive_value(combined) else sensitivity
        record_id = hashlib.sha256(f"{platform}|{conversation.id}|{turn.id}".encode("utf-8")).hexdigest()[:24]
        records.append({
            "id": record_id,
            "source_platform": platform,
            "source_conversation_id": conversation.id,
            "source_turn_ids": [turn.id] + ([answer.id] if answer else []),
            "source_date": turn.created_at or conversation.created_at,
            "conversation_title": conversation.title,
            "question": redact(turn.content),
            "question_class": classify_question(turn.content),
            "projects": [project] if project else [],
            "topics": topics_for(combined),
            "assistant_response_excerpt": redact(answer.content[:1200]) if answer else "",
            "confirmed_conclusions": [],
            "decisions": [],
            "action_items": [],
            "unresolved_questions": [] if answer else [redact(turn.content)],
            "reusable_preferences": [],
            "entities": topics_for(combined),
            "relationships": [],
            "sensitivity": record_sensitivity,
            "review_status": "draft",
            "source_export_hash": source_hash,
        })
    return records


def yaml_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def safe_filename(value: str) -> str:
    clean = re.sub(r"[\\/:*?\"<>|]", "-", value).strip(" .")
    return clean[:80] or "未命名会话"


def render_review_note(conversation: Conversation, records: list[dict], platform: str, source_hash: str, project: str | None, sensitivity: str) -> str:
    frontmatter = {
        "type": "conversation-knowledge",
        "status": "draft",
        "source_platform": platform,
        "source_conversation_id": conversation.id,
        "source_date": conversation.created_at or "",
        "projects": [project] if project else [],
        "topics": sorted({topic for record in records for topic in record["topics"]}),
        "sensitivity": sensitivity,
        "reviewed": False,
        "source_export_hash": source_hash,
    }
    lines = ["---", *[f"{key}: {yaml_value(value)}" for key, value in frontmatter.items()], "---", "", f"# {conversation.title}", "", "> 自动提炼的待审核会话知识。原始导出保留在本地私有区；结论、决策和偏好需人工确认。", ""]
    for index, record in enumerate(records, 1):
        lines.extend([
            f"## {index}. {record['question'][:100].replace(chr(10), ' ')}",
            "",
            f"- 问题分类：`{record['question_class']}`",
            f"- 主题：{', '.join(record['topics']) or '待标注'}",
            f"- 敏感级别：`{record['sensitivity']}`",
            f"- 来源轮次：{', '.join(record['source_turn_ids'])}",
            "",
            "### 原始问题",
            "",
            record["question"],
            "",
            "### 助手回复摘录",
            "",
            record["assistant_response_excerpt"] or "未找到对应回复。",
            "",
            "### 人工审核区",
            "",
            "- 已确认结论：",
            "- 决策与理由：",
            "- 后续行动：",
            "- 未解决问题：",
            "- 可建立关系：",
            "",
        ])
    return "\n".join(lines)


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def import_export(path: Path, vault: Path, local_dir: Path, project: str | None = None, sensitivity: str = "internal") -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    source_hash = sha256_file(path)
    run_dir = local_dir / "conversations" / source_hash[:16]
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        report = json.loads(manifest_path.read_text(encoding="utf-8"))
        return {**report, "duplicate": True}
    platform, conversations = read_export(path)
    raw_dir = vault / "95_Private" / "Conversation_Exports"
    raw_dir.mkdir(parents=True, exist_ok=True)
    archived = raw_dir / f"{source_hash[:12]}-{path.name}"
    if not archived.exists():
        shutil.copy2(path, archived)
    run_dir.mkdir(parents=True, exist_ok=True)
    normalized = []
    notes = []
    question_count = 0
    for conversation in conversations:
        records = question_records(conversation, platform, source_hash, project, sensitivity)
        if not records:
            continue
        normalized_conversation = asdict(conversation)
        for turn in normalized_conversation["turns"]:
            turn["content"] = redact(turn["content"])
        normalized.append({"conversation": normalized_conversation, "questions": records})
        note_sensitivity = "restricted" if sensitivity == "restricted" or any(record["sensitivity"] == "restricted" for record in records) else sensitivity
        destination_root = vault / "95_Private" / "Conversations" if note_sensitivity == "restricted" else vault / "70_Conversations" / "Inbox"
        date_prefix = (conversation.created_at or dt.date.today().isoformat())[:10]
        destination = destination_root / f"{date_prefix}-{safe_filename(conversation.title)}-{conversation.id[:8]}.md"
        write_text_atomic(destination, render_review_note(conversation, records, platform, source_hash, project, note_sensitivity))
        notes.append(str(destination))
        question_count += len(records)
    write_text_atomic(run_dir / "normalized.json", json.dumps(normalized, ensure_ascii=False, indent=2))
    report = {
        "source": str(path),
        "source_hash": source_hash,
        "platform": platform,
        "conversations": len(normalized),
        "questions": question_count,
        "notes": notes,
        "raw_archive": str(archived),
        "normalized": str(run_dir / "normalized.json"),
        "duplicate": False,
    }
    write_text_atomic(manifest_path, json.dumps(report, ensure_ascii=False, indent=2))
    return report


def build_parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path)
    parser.add_argument("--vault", type=Path, default=root.parent / "commercial-insight-vault")
    parser.add_argument("--local-dir", type=Path, default=root / "local")
    parser.add_argument("--project", choices=["project-a", "project-b", "project-c", "project-d"])
    parser.add_argument("--sensitivity", choices=["public", "internal", "restricted"], default="internal")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = import_export(
            args.export.expanduser().resolve(),
            args.vault.expanduser().resolve(),
            args.local_dir.expanduser().resolve(),
            args.project,
            args.sensitivity,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(f"Conversation import failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
