# Seedance Video Generation

## Decision

Use ByteDance Seedance 2.0 through the Volcengine Ark API as the first video-generation provider. Seedance is downstream of content analysis and script approval; it is not used to understand uploaded videos.

The product still prioritizes the founder's real voice and judgment. Seedance should initially generate supplementary shots, product scenes, transitions, and visual demonstrations rather than replace the full personal-brand video.

## API Workflow

1. The user reviews the content draft and writes a dedicated visual prompt.
2. The UI displays model, ratio, duration, and resolution before submission.
3. A confirmation dialog warns that the API call may incur charges.
4. The server calls `POST /api/v3/contents/generations/tasks` and stores the returned task ID.
5. The user refreshes task status. When it succeeds, the server downloads the temporary result URL immediately.

```text
local/
├── video_jobs/<task-id>/job.json
└── video_outputs/<task-id>/video.mp4
```

Both directories are excluded from Git.

## Configuration

```bash
ARK_API_KEY=your-key
SEEDANCE_VIDEO_GENERATION_MODEL=doubao-seedance-2-0-260128
```

The default endpoint and model ID are defined in `config/model_providers.json`. Override the model through `.env` if the account uses a dedicated endpoint ID or a newer model version.

## Current Scope

- Text-to-video submission.
- Up to four HTTPS or `asset://` reference-image addresses.
- Ratios: 9:16, 16:9, 1:1, 4:3, 3:4, 21:9, adaptive.
- Durations exposed in the UI: 5, 10, and 15 seconds.
- Resolutions: 480p, 720p, and 1080p.
- Manual status refresh and automatic local download after success.

Local image upload to Volcengine asset storage, prompt benchmarking, cost estimates, cancellation, callbacks, and multi-shot orchestration remain later work.

## Review Boundary

Before publishing, manually review brand fidelity, factual claims, generated people, logos, music and voice rights, platform AIGC labeling rules, and whether any prior-employer or customer information entered the prompt.

Official references:

- https://www.volcengine.com/docs/82379/1520757
- https://api.volcengine.com/api-docs/view?action=GetContentsGenerationsTask&serviceCode=ark&version=2024-01-01
