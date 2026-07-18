#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$repo_root"

mkdir -p local/logs
python3 scripts/social_collector.py
python3 scripts/knowledge_store.py index
