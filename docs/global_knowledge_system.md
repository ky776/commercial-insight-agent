# Global Personal Knowledge System

## Confirmed Decisions

- ChatGPT official data export is an optional conversation source.
- Codex and ChatGPT raw conversation exports remain local-only.
- Former-employer internal material uses the same Obsidian Vault under `95_Private/`.
- `95_Private/` is excluded from Git in its entirety.
- A, B, C, and D are four separate real projects. Stable IDs are created before final display names are known.
- The knowledge graph stores distilled questions, decisions, conclusions, tasks, and relationships rather than every raw message.

## Four Storage Layers

1. Raw archive: immutable exports and original files in local-only storage.
2. Normalized records: parsed turns, extracted text, hashes, and processing state under ignored `local/` paths.
3. Reviewed knowledge: atomic Obsidian notes under `60_Projects`, `70_Conversations`, and existing domain folders.
4. Operational manuals: verified procedures under `80_Manuals` with project and source links.

## Conversation Pipeline

```text
Official export or selected transcript
  -> normalize conversations and turns
  -> classify user questions
  -> extract conclusions, decisions, tasks, entities, and relationships
  -> deduplicate by meaning and source identity
  -> route restricted content to 95_Private
  -> human review
  -> write atomic notes and Obsidian links
```

Raw conversations are never used as a permanent preference profile. A reusable preference remains a candidate until the user explicitly confirms it.

## Project Manual Pipeline

The project registry is `config/project_registry.yaml`. Each project can link a local path, repository, Vault directory, and initial manual scope.

Manual generation may read verified repository files, environment variable names, prior decisions, and successful commands. It must not copy secret values. Every operational manual records `verified_at`; unverified generated steps remain drafts.

## Batch Material Pipeline

```text
Local drop folder
  -> hash and deduplicate
  -> parse or OCR by media type
  -> classify sensitivity before model use
  -> extract facts with page/section evidence
  -> separate source opinion and model inference
  -> propose tags, relationships, and destination
  -> human review and redaction
  -> store in synchronized or local-only Vault area
```

Former-employer material defaults to `restricted`. It is not sent to an external model and is not synchronized to GitHub. A derived insight can leave the private area only after explicit de-identification and review.

## Delivery Phases

- P0: directories, privacy policy, schemas, and project registry.
- P1: ChatGPT/Codex export importer and conversation review queue.
- P2: project scanner and verified manual generator.
- P3: batch document ingestion, classification, and review UI.
- P4: graph quality evaluation, duplicate merging, and retrieval tuning.
