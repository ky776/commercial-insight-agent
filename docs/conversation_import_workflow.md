# Conversation Import Workflow

## Supported Inputs

- ChatGPT official data export ZIP containing `conversations.json`
- ChatGPT `conversations.json`
- Generic Codex/chat JSON or JSONL containing role/content turns
- Markdown or text using `User`, `Assistant`, `用户`, `助手`, `ChatGPT`, or `Codex` headings

## Import

```bash
python3 scripts/conversation_importer.py "/absolute/path/to/export.zip" \
  --project project-a \
  --sensitivity internal
```

For former-employer or customer conversations:

```bash
python3 scripts/conversation_importer.py "/absolute/path/to/conversation.md" \
  --project project-a \
  --sensitivity restricted
```

## Storage

- Immutable source copy: `../commercial-insight-vault/95_Private/Conversation_Exports/`
- Normalized local records: `local/conversations/<source-hash>/normalized.json`
- Internal review notes: `../commercial-insight-vault/70_Conversations/Inbox/`
- Restricted review notes: `../commercial-insight-vault/95_Private/Conversations/`

The importer deduplicates complete export files by SHA-256. Re-importing an unchanged export returns the existing manifest.

## Review Boundary

The first version performs deterministic local extraction only. It classifies each user turn, links a selected project, identifies coarse topics, pairs it with the next assistant response, and creates an Obsidian review section.

It does not treat assistant text as confirmed fact, automatically learn preferences, or publish restricted material. Decisions, conclusions, action items, relationships, and reusable preferences remain empty until human review or a later explicitly approved reasoning step.
