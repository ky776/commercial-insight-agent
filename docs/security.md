# Security And Sync Boundary

## Data Classes

### Public

Prompts, schemas, generic methods, and non-sensitive code may live in the public Agent repository.

### Internal

Personal opinions, public-source notes, topic ideas, and unpublished drafts may live in the private Vault repository.

### Restricted

Client raw data, credentials, contracts, account exports, unpublished financial data, and identifiable customer information must remain in ignored local storage or a separately encrypted system.

## Git Rules

- Keep the Vault repository private.
- Ignore `.obsidian/`, private attachments, media, exports, databases, and environment files.
- Review `git status --short` before every commit.
- Never use `git add .` until ignored and untracked files have been reviewed.
- Treat Git history as durable. Removing a file in a later commit does not remove the earlier copy.
- Rotate any credential immediately if it is committed, even to a private repository.

## Local Rules

- Enable macOS FileVault.
- Keep API keys in environment variables or the system keychain.
- Store client materials under `local/` with restricted filesystem permissions.
- Back up the Vault and `local/` separately using an encrypted backup destination.

## Agent Rules

- Send only the minimum required source excerpts to external model APIs.
- Record which source IDs were sent in each run.
- Require explicit approval before restricted client material is sent to any external provider.
- Redact personal identifiers and account credentials before analysis.
- Do not upload raw source media merely to summarize existing cached text.
