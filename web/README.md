# Local Founder Workspace Prototype

Open `index.html` directly in a browser. The prototype has no network dependencies and does not upload selected files.

Implemented flow:

```text
text / URL / local file metadata
  -> mode and privacy selection
  -> compact editable task brief
  -> browser-local task save
  -> Markdown export
```

Text-like files up to 2 MB are read locally for brief generation. PDF, image, audio, and video files contribute metadata only in this prototype.

Browser local storage is temporary prototype state, not the final SQLite storage defined in `docs/storage_architecture.md`.
