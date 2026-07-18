#!/usr/bin/env python3
"""Build and query a local SQLite index for the Obsidian knowledge Vault."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path


FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
QUERY_SPLIT_RE = re.compile(r"[\s，。；：！？、,.!?;:（）()\[\]【】/]+")
GENERIC_TERMS = {
    "分析", "报告", "这份报告", "核心观点", "提炼", "生成", "内容", "自媒体",
    "文章", "大纲", "视频", "脚本", "资料", "素材", "一个", "相关", "分析这份报告",
    "提炼核心观点", "生成自媒体内容", "用户任务描述", "洞见研报DJyanbao", "com", "pdf", "MB",
}
DOMAIN_TERMS = (
    "广告效果", "获客成本", "平台流量", "企业号", "本地生活", "电商", "短剧", "漫剧",
    "商单", "代理商", "归因", "结算", "品牌", "内容生态", "AI营销", "AI应用", "AI算力",
    "Agent", "商业化", "软件行业", "生成式AI", "大模型", "数据治理", "网络安全", "IT运维",
)


@dataclass
class Chunk:
    heading: str
    body: str
    ordinal: int


def parse_scalar(value: str):
    value = value.strip()
    if not value:
        return None
    if value == "[]":
        return []
    if value.startswith("[") and value.endswith("]"):
        return [item.strip().strip("\"'") for item in value[1:-1].split(",") if item.strip()]
    return value.strip("\"'")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    data = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = parse_scalar(value)
    return data, text[match.end():]


def note_title(body: str, fallback: str) -> str:
    match = HEADING_RE.search(body)
    return match.group(2).strip() if match else fallback


def split_large_text(text: str, limit: int = 2400, overlap: int = 180) -> list[str]:
    clean = text.strip()
    if not clean:
        return []
    parts = []
    cursor = 0
    while cursor < len(clean):
        end = min(cursor + limit, len(clean))
        if end < len(clean):
            boundary = max(clean.rfind("\n", cursor, end), clean.rfind("。", cursor, end))
            if boundary > cursor + limit // 2:
                end = boundary + 1
        parts.append(clean[cursor:end].strip())
        if end >= len(clean):
            break
        cursor = max(end - overlap, cursor + 1)
    return [part for part in parts if part]


def chunk_markdown(body: str) -> list[Chunk]:
    matches = list(HEADING_RE.finditer(body))
    sections: list[tuple[str, str]] = []
    if not matches:
        sections.append(("正文", body))
    else:
        prefix = body[:matches[0].start()].strip()
        if prefix:
            sections.append(("导言", prefix))
        stack: list[tuple[int, str]] = []
        for index, match in enumerate(matches):
            level = len(match.group(1))
            title = match.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
            content = body[match.end():end].strip()
            if content:
                sections.append((" / ".join(item[1] for item in stack), content))

    chunks = []
    ordinal = 0
    for heading, section in sections:
        for part in split_large_text(section):
            chunks.append(Chunk(heading=heading, body=part, ordinal=ordinal))
            ordinal += 1
    return chunks


def connect(database: Path) -> sqlite3.Connection:
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS knowledge_notes (
            path TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            note_type TEXT,
            status TEXT,
            topics TEXT NOT NULL,
            confidence TEXT,
            source_url TEXT,
            content_hash TEXT NOT NULL,
            modified_ns INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            id INTEGER PRIMARY KEY,
            note_path TEXT NOT NULL,
            title TEXT NOT NULL,
            heading TEXT NOT NULL,
            body TEXT NOT NULL,
            ordinal INTEGER NOT NULL,
            FOREIGN KEY(note_path) REFERENCES knowledge_notes(path)
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_fts USING fts5(
            title, heading, body, note_path UNINDEXED, tokenize='unicode61'
        );
        """
    )
    return connection


def discover_notes(vault: Path) -> list[Path]:
    notes = []
    for path in sorted(vault.rglob("*.md")):
        relative = path.relative_to(vault)
        if any(part in {".obsidian", ".trash", "exports"} for part in relative.parts):
            continue
        if path.name == "README.md" or (relative.parts and relative.parts[0] == "90_Templates"):
            continue
        if relative.parts[:2] == ("attachments", "private"):
            continue
        notes.append(path)
    return notes


def rebuild_index(vault: Path, database: Path) -> dict:
    if not vault.is_dir():
        raise FileNotFoundError(f"Vault directory not found: {vault}")
    connection = connect(database)
    connection.execute("DELETE FROM knowledge_chunks_fts")
    connection.execute("DELETE FROM knowledge_chunks")
    connection.execute("DELETE FROM knowledge_notes")

    note_count = 0
    chunk_count = 0
    for note_path in discover_notes(vault):
        text = note_path.read_text(encoding="utf-8")
        metadata, body = parse_frontmatter(text)
        relative = note_path.relative_to(vault).as_posix()
        title = note_title(body, note_path.stem)
        topics = metadata.get("topics") or []
        if isinstance(topics, str):
            topics = [topics]
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        connection.execute(
            """INSERT INTO knowledge_notes
               (path, title, note_type, status, topics, confidence, source_url, content_hash, modified_ns)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                relative, title, metadata.get("type"), metadata.get("status"),
                json.dumps(topics, ensure_ascii=False), metadata.get("confidence"),
                metadata.get("source_url"), digest, note_path.stat().st_mtime_ns,
            ),
        )
        for chunk in chunk_markdown(body):
            cursor = connection.execute(
                """INSERT INTO knowledge_chunks (note_path, title, heading, body, ordinal)
                   VALUES (?, ?, ?, ?, ?)""",
                (relative, title, chunk.heading, chunk.body, chunk.ordinal),
            )
            connection.execute(
                """INSERT INTO knowledge_chunks_fts (rowid, title, heading, body, note_path)
                   VALUES (?, ?, ?, ?, ?)""",
                (cursor.lastrowid, title, chunk.heading, chunk.body, relative),
            )
            chunk_count += 1
        note_count += 1
    connection.commit()
    connection.close()
    return {"vault": str(vault), "database": str(database), "notes": note_count, "chunks": chunk_count}


def query_terms(query: str) -> list[str]:
    raw = [term.strip() for term in QUERY_SPLIT_RE.split(query) if term.strip()]
    terms = [term for term in DOMAIN_TERMS if term.casefold() in query.casefold()]
    for term in raw:
        if term in GENERIC_TERMS or len(term) < 2:
            continue
        if len(term) <= 16:
            terms.append(term)
    return list(dict.fromkeys(terms))[:12]


def score_chunk(row: sqlite3.Row, terms: list[str], fts_ids: set[int]) -> float:
    title = row["title"].casefold()
    heading = row["heading"].casefold()
    body = row["body"].casefold()
    topics = row["topics"].casefold()
    score = 1.5 if row["id"] in fts_ids else 0.0
    for term in terms:
        needle = term.casefold()
        if needle in title:
            score += 8.0
        if needle in heading:
            score += 5.0
        if needle in topics:
            score += 4.0
        score += min(body.count(needle), 5) * 1.2
    confidence = row["confidence"]
    if confidence == "high":
        score += 0.5
    elif confidence == "low":
        score -= 0.25
    return score


def excerpt(body: str, terms: list[str], limit: int = 260) -> str:
    positions = [body.casefold().find(term.casefold()) for term in terms]
    positions = [position for position in positions if position >= 0]
    center = min(positions) if positions else 0
    start = max(center - 70, 0)
    end = min(start + limit, len(body))
    text = re.sub(r"\s+", " ", body[start:end]).strip()
    return f"…{text}" if start else text


def search_index(
    database: Path,
    query: str,
    top_k: int = 6,
    note_type: str | None = None,
    status: str | None = None,
) -> list[dict]:
    if not database.exists():
        raise FileNotFoundError(f"Index not found: {database}. Run the index command first.")
    terms = query_terms(query)
    if not terms:
        return []
    connection = connect(database)
    fts_ids: set[int] = set()
    fts_query = " OR ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms)
    try:
        fts_ids = {row[0] for row in connection.execute(
            "SELECT rowid FROM knowledge_chunks_fts WHERE knowledge_chunks_fts MATCH ? LIMIT 80",
            (fts_query,),
        )}
    except sqlite3.OperationalError:
        fts_ids = set()

    clauses = []
    params: list[str] = []
    if note_type:
        clauses.append("n.note_type = ?")
        params.append(note_type)
    if status:
        clauses.append("n.status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = connection.execute(
        f"""SELECT c.id, c.note_path, c.title, c.heading, c.body, c.ordinal,
                   n.note_type, n.status, n.topics, n.confidence, n.source_url
            FROM knowledge_chunks c
            JOIN knowledge_notes n ON n.path = c.note_path
            {where}""",
        params,
    ).fetchall()
    ranked = []
    for row in rows:
        score = score_chunk(row, terms, fts_ids)
        if score <= 0:
            continue
        heading_anchor = row["heading"].split(" / ")[-1]
        ranked.append({
            "path": row["note_path"],
            "title": row["title"],
            "heading": row["heading"],
            "citation": f"[[{row['note_path']}#{heading_anchor}]]",
            "type": row["note_type"],
            "status": row["status"],
            "confidence": row["confidence"],
            "source_url": row["source_url"],
            "score": round(score, 2),
            "excerpt": excerpt(row["body"], terms),
        })
    connection.close()
    ranked.sort(key=lambda item: (-item["score"], item["path"], item["heading"]))
    return ranked[:top_k]


def index_status(database: Path) -> dict:
    if not database.exists():
        return {"ready": False, "database": str(database), "notes": 0, "chunks": 0}
    connection = connect(database)
    notes = connection.execute("SELECT COUNT(*) FROM knowledge_notes").fetchone()[0]
    chunks = connection.execute("SELECT COUNT(*) FROM knowledge_chunks").fetchone()[0]
    connection.close()
    return {"ready": True, "database": str(database), "notes": notes, "chunks": chunks}


def default_paths() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[1]
    return root.parent / "commercial-insight-vault", root / "local" / "app.sqlite3"


def build_parser() -> argparse.ArgumentParser:
    vault, database = default_paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=vault)
    parser.add_argument("--database", type=Path, default=database)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("index")
    subparsers.add_parser("status")
    search = subparsers.add_parser("search")
    search.add_argument("query")
    search.add_argument("--top-k", type=int, default=6)
    search.add_argument("--type", dest="note_type")
    search.add_argument("--status")
    search.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    vault = args.vault.expanduser().resolve()
    database = args.database.expanduser().resolve()
    try:
        if args.command == "index":
            print(json.dumps(rebuild_index(vault, database), ensure_ascii=False, indent=2))
        elif args.command == "status":
            print(json.dumps(index_status(database), ensure_ascii=False, indent=2))
        else:
            results = search_index(database, args.query, args.top_k, args.note_type, args.status)
            if args.json:
                print(json.dumps(results, ensure_ascii=False, indent=2))
            elif not results:
                print("No relevant knowledge chunks found.")
            else:
                for index, item in enumerate(results, 1):
                    print(f"{index}. {item['title']} · {item['heading']} · score {item['score']}")
                    print(f"   {item['citation']}")
                    print(f"   {item['excerpt']}")
        return 0
    except (OSError, sqlite3.Error, UnicodeError) as exc:
        print(f"Knowledge store failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
