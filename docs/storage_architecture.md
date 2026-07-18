# Local-First Storage Architecture

## Decision

Use three storage layers with different responsibilities:

- Obsidian Markdown: durable knowledge and human-readable content
- SQLite: jobs, runs, artifact versions, source metadata, and model usage
- Local filesystem: original and generated media

Do not store binary media in Git. Do not treat SQLite as the source of truth for knowledge notes.

## Local Paths

All private runtime data lives under the ignored `local/` directory:

```text
local/
├── app.sqlite3
├── inputs/{job_id}/
├── processed/{job_id}/
├── outputs/{job_id}/{artifact_id}/
├── cache/{content_hash}/
└── logs/
```

An output directory may contain:

```text
brief.json
analysis.md
script-v001.md
script-v002.md
captions-v001.txt
shot-list-v001.md
manifest.json
```

## SQLite Responsibilities

The MVP database stores:

- `jobs`: user intent, state, timestamps, and privacy class
- `sources`: paths, URLs, hashes, media types, and parse status
- `runs`: processor/model, status, timing, usage, and errors
- `artifacts`: type, version, local path, approval status, and parent artifact
- `vault_links`: artifact-to-note relationships
- `decisions`: confirmed choices that should survive later runs

## File Integrity

- Calculate a SHA-256 hash for every input.
- Reuse cached extraction only when the hash and parser version match.
- Store paths relative to the workspace root when possible.
- Write generated files to a temporary name and rename only after completion.
- Never overwrite an approved artifact; create the next version.

## Future Multi-User Upgrade

When external users are introduced, replace SQLite with PostgreSQL and move binary media to private object storage with encryption and signed URLs. Keep the Vault as the founder's editorial knowledge system until a separate permission model is proven necessary.
