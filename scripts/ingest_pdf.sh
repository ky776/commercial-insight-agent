#!/bin/sh
set -eu

if python3 -c 'import pdfplumber' >/dev/null 2>&1; then
  exec python3 "$(dirname "$0")/ingest_pdf.py" "$@"
fi

bundled_python="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
if [ -x "$bundled_python" ]; then
  exec "$bundled_python" "$(dirname "$0")/ingest_pdf.py" "$@"
fi

printf '%s\n' 'PDF parser not found. Install pdfplumber with: python3 -m pip install pdfplumber' >&2
exit 1
