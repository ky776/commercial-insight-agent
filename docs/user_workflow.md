# Founder Workspace User Flow

## Product Boundary

The MVP serves one operator: the founder. Customers receive exported deliverables and do not log in to the Agent.

The product is a task-oriented workspace, not a general chat application. Chat is available for local revisions, but every action belongs to a visible job and artifact.

## Primary Flow

### 1. Capture

The user can:

- Paste text or a URL
- Select one or more local files
- Drag in video, audio, images, GIFs, PDF, Markdown, or text files
- Choose `快速收集` or `结构化任务`

The system creates a job immediately and copies source files into `local/inputs/{job_id}/`.

### 2. Parse

The system performs only the processing required by the media type:

- Video/audio: metadata, transcription, optional keyframes
- Image/GIF: OCR, visual summary, frame selection when needed
- PDF/article: text extraction, headings, tables, and source metadata
- URL: title, publisher, date, canonical URL, and readable content

Each expensive result is cached by content hash.

### 3. Confirm Brief

`brief-router` produces an editable brief containing goal, audience, inputs, constraints, deliverable, assumptions, knowledge queries, and budget profile.

The user can approve it, edit any field, or answer no more than three blocking questions.

### 4. Analyze

The Agent creates a material card, searches the Obsidian Vault, separates facts from inference and opinion, and shows exact source-note citations.

The user can exclude a source, change the analysis angle, or save the result to the Vault.

### 5. Generate

The user selects one output:

- Short-video script
- WeChat article outline
- Industry daily or weekly digest
- Infographic structure
- Material analysis card

For short video, the MVP generates title options, hook, spoken script, shot list, captions, B-roll suggestions, and cover copy. It does not generate a complete video.

### 6. Review And Revise

The user can edit directly or request a scoped revision:

- Rewrite selected text
- Change tone or audience
- Shorten or expand
- Strengthen evidence
- Replace the opening hook
- Regenerate one section

Every revision creates an artifact version. The system never overwrites an approved version silently.

### 7. Export And Learn

The user exports Markdown, plain text, or subtitle-friendly text. Published links and performance data are added manually later.

Approved reusable insights are saved to `30_Insights`; final drafts are saved to `40_Content`; anonymized client learning is saved to `50_Showcase`.

## Job States

```text
captured
  -> parsing
  -> brief_review
  -> ready
  -> analyzing
  -> generation_review
  -> generating
  -> draft_ready
  -> approved
  -> exported
  -> archived
```

Any processing state may become `failed` or `needs_input`. Retrying creates a new run under the same job.

## Success Criteria

A successful run must provide:

- A visible source list
- A confirmed brief
- An auditable generated artifact
- Clear unresolved facts or risks
- A stable local output path
- A usable next action
