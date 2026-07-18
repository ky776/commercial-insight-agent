# Local Knowledge Workflow

This stage turns PDFs and Obsidian notes into locally searchable evidence. No source content is sent to an external model.

## 1. Ingest A PDF

Use a Python environment that provides `pdfplumber` or `pypdf`:

```bash
sh scripts/ingest_pdf.sh "/absolute/path/report.pdf" \
  --topic "AI应用" \
  --topic "商业化"
```

The wrapper uses the current Python environment when `pdfplumber` is available and otherwise checks the bundled Codex runtime. The command creates a Markdown source note under `../commercial-insight-vault/10_Sources`. The original PDF remains outside Git. Automatically extracted text is marked as unreviewed.

## 2. Build The Local Index

```bash
python3 scripts/knowledge_store.py index
python3 scripts/knowledge_store.py status
```

The SQLite database is written to the ignored path `local/app.sqlite3`. Rebuilding the index does not modify the Vault. README files and `90_Templates` are excluded from retrieval.

## 3. Search With Citations

```bash
python3 scripts/knowledge_store.py search "AI应用 Agent 商业化" --type source
```

Each result includes an Obsidian citation such as `[[10_Sources/note.md#heading]]`, an excerpt, metadata, and a relevance score.

## 4. Retrieve Evidence For A Brief

```bash
python3 scripts/brief_retrieve.py "/absolute/path/task-brief.md"
```

The command writes `evidence.md` and `evidence.json` under the ignored directory `local/outputs/{task}/`. It derives useful domain terms from the goal, knowledge queries, and input filenames, then retrieves up to six cited chunks.

## Current Boundary

- Chinese lexical retrieval and SQLite FTS5 are implemented.
- PDF text extraction is local and cached only through the resulting Vault note.
- Images and charts inside a PDF are not interpreted yet.
- Reasoning-model synthesis is the next layer and must consume only the returned evidence chunks.
