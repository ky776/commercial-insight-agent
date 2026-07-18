#!/usr/bin/env python3
"""Merge a saved task brief with a delta and report changed fields."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


CJK_RE = re.compile(r"[\u3400-\u9fff]")


def merge(base, delta, path=""):
    if not isinstance(base, dict) or not isinstance(delta, dict):
        return delta, [path or "$root"]

    result = dict(base)
    changed = []
    for key, value in delta.items():
        field_path = f"{path}.{key}" if path else key
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key], nested = merge(result[key], value, field_path)
            changed.extend(nested)
        elif result.get(key) != value:
            result[key] = value
            changed.append(field_path)
    return result, changed


def estimate_tokens(value) -> int:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    cjk = len(CJK_RE.findall(text))
    other = len(re.sub(r"\s+", "", CJK_RE.sub("", text)))
    return round(cjk * 1.5 + other / 4)


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--delta", type=Path, required=True)
    args = parser.parse_args()

    merged, changed = merge(load_json(args.base), load_json(args.delta))
    output = {
        "brief": merged,
        "changed_fields": changed,
        "approximate_tokens": estimate_tokens(merged),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
