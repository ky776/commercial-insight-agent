# External Model Provider API

## MVP Decision

Use a provider adapter layer instead of embedding local model capabilities.

- Language and reasoning: OpenAI Responses plus OpenAI-compatible DeepSeek and Qwen endpoints.
- Video understanding: Qwen as the China-first default; Gemini as the second native multimodal adapter.
- Video generation: ByteDance Seedance 2.0 through Volcengine Ark after script review.
- Local responsibilities: storage, SHA-256 deduplication, privacy gate, routing, cache, version history, and Obsidian write-back.

Provider metadata lives in `config/model_providers.json`. Secrets live only in `.env`.

## Setup

```bash
cp .env.example .env
```

Fill only the keys you use, then restart:

```bash
./scripts/run_workspace.sh
```

The workbench disables providers whose key is missing. It never displays or logs key values.

## Privacy Gate

| Material | External API behavior |
| --- | --- |
| `public` | Allowed after the user selects a provider |
| `internal` | Allowed after the user selects a provider |
| `restricted` | Blocked until a per-request confirmation |

For prior-employer and customer material, `restricted` should be the default. API access does not make disclosure compliant; use only a provider and account approved for that material.

## Current Adapter Contract

Each adapter resolves a capability (`text`, `reasoning`, `image`, `video`, or `audio_video`), model, endpoint, and API-key environment variable. Provider-specific request formats stay behind `scripts/model_providers.py`.

The first version sends media inline up to 20 MB. Provider file upload, asynchronous jobs, cost estimation, retry policy, and object-storage lifecycle are next-stage work.

Seedance uses a separate asynchronous generation adapter. Its job records and downloaded MP4 files remain under `local/video_jobs/` and `local/video_outputs/`.
