#!/usr/bin/env python3
"""Extract a PDF into an auditable Obsidian source note."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path


REPORT_SUFFIX_RE = re.compile(r"【洞见研报[^】]*】", re.IGNORECASE)
PUBLISHER_RE = re.compile(r"^【([^】]+)】")


def load_pdf_reader():
    try:
        import pdfplumber

        return "pdfplumber", pdfplumber
    except ImportError:
        try:
            import pypdf

            return "pypdf", pypdf
        except ImportError as exc:
            raise RuntimeError(
                "PDF parser is unavailable. Run this command with the bundled Codex Python runtime "
                "or install pdfplumber."
            ) from exc


def extract_pages(pdf_path: Path) -> tuple[str, list[str]]:
    engine, module = load_pdf_reader()
    pages = []
    if engine == "pdfplumber":
        with module.open(pdf_path) as document:
            pages = [(page.extract_text() or "").strip() for page in document.pages]
    else:
        document = module.PdfReader(str(pdf_path))
        pages = [(page.extract_text() or "").strip() for page in document.pages]
    return engine, pages


def clean_title(stem: str) -> str:
    return REPORT_SUFFIX_RE.sub("", stem).strip()


def infer_publisher(title: str) -> str:
    match = PUBLISHER_RE.match(title)
    return match.group(1) if match else ""


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def build_note(pdf_path: Path, title: str, publisher: str, engine: str, pages: list[str], topics: list[str]) -> str:
    today = dt.date.today().isoformat()
    topic_list = ", ".join(yaml_string(topic) for topic in topics)
    sections = []
    for index, text in enumerate(pages, 1):
        sections.append(f"### 第 {index} 页\n\n{text or '[本页未提取到文本]'}")
    extracted = "\n\n".join(sections)
    return f"""---
type: source
status: inbox
source_type: industry_report
publisher: {yaml_string(publisher)}
author:
source_url:
source_file: {yaml_string(str(pdf_path))}
published_at:
accessed_at: {today}
topics: [{topic_list}]
tags: [PDF自动提取]
confidence: medium
extraction_engine: {engine}
extraction_reviewed: false
---

# {title}

> 本笔记由本地工具自动提取。引用或发布前，请对照 PDF 原文复核页码、数据和图表。

## 核心事实

待人工或 Agent 基于原文提炼。

## 关键数据

待人工或 Agent 基于原文提炼。

## 可转化内容角度

待结合目标受众和个人观点库生成。

## PDF 提取文本

{extracted}
"""


def ingest(pdf_path: Path, vault: Path, output: Path | None, topics: list[str], force: bool) -> Path:
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("Input must be a PDF file")
    if not vault.is_dir():
        raise FileNotFoundError(f"Vault not found: {vault}")
    title = clean_title(pdf_path.stem)
    destination = output or (vault / "10_Sources" / f"{title}.md")
    destination = destination if destination.is_absolute() else vault / destination
    if destination.exists() and not force:
        raise FileExistsError(f"Note already exists: {destination}. Use --force to replace it.")
    engine, pages = extract_pages(pdf_path)
    note = build_note(pdf_path, title, infer_publisher(title), engine, pages, topics)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(note, encoding="utf-8")
    temporary.replace(destination)
    return destination


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--vault", type=Path, default=root.parent / "commercial-insight-vault")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--topic", action="append", default=[])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        destination = ingest(
            args.pdf.expanduser().resolve(), args.vault.expanduser().resolve(), args.output,
            args.topic, args.force,
        )
        print(destination)
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"PDF ingestion failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
