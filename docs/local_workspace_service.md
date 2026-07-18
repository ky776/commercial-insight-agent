# Local Workspace Service

The local service connects the browser workspace to the private Obsidian evidence index and content generators.

## Start

```bash
cd /Users/ky/Documents/Codex/2026-07-01/wo/commercial-insight-agent
./scripts/run_workspace.sh
```

Open `http://127.0.0.1:4173`. Do not open `web/index.html` directly when retrieval or generation is needed.

## Generation Modes

- `auto`: use the configured OpenAI model for public or internal briefs; otherwise use local evidence mode.
- `evidence`: never call an external model. Build a cited working structure from local retrieval results.
- `openai`: explicitly use the configured model. Restricted material requires a separate confirmation in the UI.

The default model can be changed without modifying code:

```bash
export OPENAI_MODEL="gpt-5.6-luna"
export OPENAI_API_KEY="your-key"
./scripts/run_workspace.sh
```

Keep secrets in the shell environment or a local secret manager. Never write an API key into the Vault, browser JavaScript, Git, or a Markdown note.

## Storage

- Knowledge source: sibling private Vault `../commercial-insight-vault`
- Search index: `local/app.sqlite3`
- Generated versions: `local/outputs/<task-id>/artifact-vNNN.md`
- Generation metadata: adjacent `artifact-vNNN.json`
- Browser job list: local browser storage

The entire `local/` directory is ignored by Git. Generated drafts stay on this Mac unless they are deliberately moved to the Vault or exported.

## Review Workflow

1. Edit the Markdown working draft directly and select `保存当前版本` to create a human-authored version.
2. Enter a scoped instruction and select `按要求修改` to create a model-generated revision. The previous version remains unchanged.
3. Select any item in `版本历史` to restore it in the editor.
4. After manually checking facts, citations, and wording, select `审核通过`.
5. The approved version is saved locally and written as a new note under the private Vault's `40_Content` directory.

Approval does not publish content or sync it to a social platform. Vault Git synchronization remains a separate deliberate action.

## Security Boundary

- The HTTP server listens only on `127.0.0.1` by default.
- The API key remains server-side and is never returned by `/api/health`.
- Only retrieved evidence excerpts are sent to a cloud model, not the entire Vault.
- Restricted briefs use local evidence mode unless cloud use is explicitly selected and confirmed.
- Publishing remains manual.
