#!/usr/bin/env python3
"""Validate that the Agent can discover and read the Obsidian Vault."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)


def parse_scalar(value: str):
    value = value.strip()
    if not value:
        return None
    if value == "[]":
        return []
    if value.startswith("[") and value.endswith("]"):
        return [item.strip().strip("\"'") for item in value[1:-1].split(",") if item.strip()]
    return value.strip("\"'")


def parse_frontmatter(text: str) -> dict:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}

    data = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = parse_scalar(value)
    return data


def inspect_vault(vault_path: Path) -> dict:
    if not vault_path.is_dir():
        raise FileNotFoundError(f"Vault directory not found: {vault_path}")

    notes = []
    type_counts = Counter()
    malformed = []

    for note_path in sorted(vault_path.rglob("*.md")):
        if any(part in {".obsidian", ".trash"} for part in note_path.parts):
            continue
        text = note_path.read_text(encoding="utf-8")
        metadata = parse_frontmatter(text)
        relative_path = note_path.relative_to(vault_path).as_posix()
        note_type = metadata.get("type", "untyped")
        type_counts[note_type] += 1
        if note_path.parent.name != "90_Templates" and note_path.name not in {"README.md"}:
            missing = [field for field in ("type", "status") if not metadata.get(field)]
            if missing:
                malformed.append({"path": relative_path, "missing": missing})
        notes.append({
            "path": relative_path,
            "type": note_type,
            "status": metadata.get("status"),
            "characters": len(text),
        })

    return {
        "connected": True,
        "vault_path": str(vault_path),
        "markdown_notes": len(notes),
        "types": dict(sorted(type_counts.items())),
        "malformed_notes": malformed,
        "notes": notes,
    }


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    default_vault = repo_root.parent / "commercial-insight-vault"
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", type=Path, default=default_vault)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        report = inspect_vault(args.vault.expanduser().resolve())
    except (OSError, UnicodeError) as exc:
        print(f"Knowledge vault check failed: {exc}")
        return 1

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("Knowledge vault connected")
        print(f"Path: {report['vault_path']}")
        print(f"Markdown notes: {report['markdown_notes']}")
        print(f"Types: {report['types']}")
        print(f"Malformed notes: {len(report['malformed_notes'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
