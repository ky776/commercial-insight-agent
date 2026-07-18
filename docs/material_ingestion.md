# Material Ingestion And API Understanding

## Boundary

The workspace does not package local OCR, speech recognition, or video-understanding models. The loopback service only stores the original file, computes SHA-256, applies privacy rules, calls a user-selected external API, and caches the returned analysis.

Text and text-based PDFs may still be extracted locally because this is document parsing rather than semantic model inference. Images, audio, and video remain untouched until the user clicks `模型理解`.

## Workflow

1. The browser uploads a file to `127.0.0.1`.
2. The service stores it under `local/inputs/<capture-id>/` and writes a manifest under `local/cache/materials/<sha256>/`.
3. The user selects Qwen or Gemini and clicks `模型理解`.
4. Public and internal files are sent to the selected API. Restricted files require per-request confirmation.
5. The structured Markdown result is cached and added to the current brief context.

```text
local/
├── inputs/<capture-id>/<hash-prefix>-<filename>
└── cache/materials/<sha256>/
    ├── manifest.json
    └── analyses/<provider>-<model>-<prompt-hash>.json
```

`local/` and `.env` are excluded from Git. API keys are read from environment variables and are never returned to the browser.

## MVP Limits

- Local upload limit: 100 MB.
- Inline external API transfer: 20 MB.
- Larger media needs a provider Files API or private object-storage upload in the next iteration.
- Repeating the same file, provider, model, and prompt uses the local result cache.
- Model results remain drafts until manually reviewed and approved into Obsidian.
