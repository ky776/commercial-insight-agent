#!/usr/bin/env python3
"""Retrieve an auditable evidence pack for an exported task brief."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

try:
    from scripts.knowledge_store import default_paths, query_terms, search_index
except ModuleNotFoundError:
    from knowledge_store import default_paths, query_terms, search_index


SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def parse_brief(text: str) -> dict:
    title_match = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "未命名任务"
    sections = {}
    matches = list(SECTION_RE.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1).strip()] = text[match.end():end].strip()
    return {"goal": title, "sections": sections}


def list_items(value: str) -> list[str]:
    return [line[2:].strip() for line in value.splitlines() if line.startswith("- ") and line[2:].strip()]


def retrieval_query(brief: dict) -> str:
    sections = brief["sections"]
    candidates = [brief["goal"]]
    candidates.extend(list_items(sections.get("知识库检索词", "")))
    candidates.extend(list_items(sections.get("输入来源", "")))
    source_text = " ".join(candidates)
    source_text = re.sub(r"【洞见研报[^】]*】", " ", source_text, flags=re.IGNORECASE)
    source_text = re.sub(r"[（(]\s*[\d.]+\s*(?:KB|MB|GB)\s*[）)]", " ", source_text, flags=re.IGNORECASE)
    source_text = re.sub(r"\.(?:pdf|md|txt)\b", " ", source_text, flags=re.IGNORECASE)
    terms = query_terms(source_text)
    return " ".join(terms) or brief["goal"]


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]", "-", value).strip(" .")
    return cleaned[:60] or "task"


def render_markdown(brief_path: Path, query: str, results: list[dict]) -> str:
    generated = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    lines = [
        "---",
        "type: evidence-pack",
        f"generated_at: {generated}",
        f"brief_file: {json.dumps(str(brief_path), ensure_ascii=False)}",
        f"result_count: {len(results)}",
        "---",
        "",
        "# 检索证据包",
        "",
        "## 检索式",
        "",
        query,
        "",
        "## 证据片段",
        "",
    ]
    if not results:
        lines.extend(["未检索到相关知识片段。需要先向 Vault 添加来源，或调整检索词。", ""])
    for index, item in enumerate(results, 1):
        lines.extend([
            f"### {index}. {item['title']}",
            "",
            f"- 引用：{item['citation']}",
            f"- 类型：{item['type'] or '未标注'}",
            f"- 状态：{item['status'] or '未标注'}",
            f"- 可信度：{item['confidence'] or '未标注'}",
            f"- 相关分：{item['score']}",
            "",
            item["excerpt"],
            "",
        ])
    lines.extend([
        "## 生成前检查",
        "",
        "- [ ] 关键数字已回看 PDF 原页",
        "- [ ] 已区分报告事实、推断和个人观点",
        "- [ ] 未把证券研究结论直接改写为经营事实",
        "- [ ] 输出符合目标受众和已确认约束",
        "",
    ])
    return "\n".join(lines)


def create_evidence_pack(brief_path: Path, database: Path, output: Path | None, top_k: int) -> tuple[Path, list[dict]]:
    if not brief_path.is_file():
        raise FileNotFoundError(f"Brief not found: {brief_path}")
    brief = parse_brief(brief_path.read_text(encoding="utf-8"))
    query = retrieval_query(brief)
    results = search_index(database, query, top_k=top_k)
    root = Path(__file__).resolve().parents[1]
    destination = output or (root / "local" / "outputs" / safe_name(brief["goal"]) / "evidence.md")
    destination.parent.mkdir(parents=True, exist_ok=True)
    markdown = render_markdown(brief_path, query, results)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(markdown, encoding="utf-8")
    temporary.replace(destination)
    destination.with_name("evidence.json").write_text(
        json.dumps({"query": query, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return destination, results


def main() -> int:
    _, default_database = default_paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", type=Path)
    parser.add_argument("--database", type=Path, default=default_database)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--top-k", type=int, default=6)
    args = parser.parse_args()
    try:
        destination, results = create_evidence_pack(
            args.brief.expanduser().resolve(), args.database.expanduser().resolve(), args.output, args.top_k,
        )
        print(destination)
        print(f"Evidence chunks: {len(results)}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"Brief retrieval failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
