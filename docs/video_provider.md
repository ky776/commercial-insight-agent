# Video Generation Boundary

## MVP Decision

Do not generate complete videos in the first product version. Personal-brand trust depends on the founder's real voice, face, judgment, and delivery.

The MVP generates production support:

- Spoken script
- Shot list
- Captions
- B-roll suggestions
- Cover copy
- Optional prompts for short supplementary clips

## Provider Interface

Future video providers must implement the same job contract:

```yaml
provider:
model:
prompt:
reference_assets: []
aspect_ratio: 9:16
duration_seconds:
quality:
remote_job_id:
status:
estimated_cost:
output_path:
created_at:
completed_at:
```

The application must not expose provider-specific fields outside an advanced settings panel.

## Selection Gate

Do not choose a default provider until a 20-prompt benchmark compares:

- Chinese prompt understanding
- Brand and product fidelity
- Human motion and lip synchronization
- Vertical-video composition
- Generation time and failure rate
- API availability and commercial rights
- Cost per usable clip

Candidate APIs may include OpenAI Sora and Google Veo, plus domestic providers only after their official API access and commercial terms are verified.

Official references:

- https://platform.openai.com/docs/api-reference/videos
- https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/veo/3-0-generate-001
