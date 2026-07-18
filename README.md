# Commercial Insight Agent

A personal commercial insight agent for tracking ad platforms, creator economy, AI marketing, and brand growth signals, turning them into structured insights, content ideas, and scripts.

## Purpose

This project is an MVP workspace for a personal content research assistant. It does not log in to social accounts and does not publish content automatically.

The agent helps with:

- Tracking ad platform, creator economy, AI marketing, and brand growth signals
- Structuring information into reusable insight cards
- Generating content topics, outlines, scripts, and weekly digests
- Supporting a content-led consulting business around ad spend diagnosis and commercial growth

## Positioning

The content strategy is built around one core promise:

> Help SMB brand owners understand where ad spend, agency work, creator campaigns, and conversion workflows are leaking value.

The agent serves as a research assistant, not as a replacement for human judgment. All facts, sensitive claims, and final opinions must be reviewed manually before publishing.

## MVP Scope

The first version focuses on:

- Daily information collection
- Structured insight extraction
- Topic generation
- Topic scoring
- Short video script drafts
- WeChat article outlines
- Weekly industry digests
- Obsidian knowledge-base retrieval with auditable note citations
- Structured brief routing to reduce repeated context and clarification
- Local-first job, artifact, and media storage boundaries

Out of scope for the first version:

- Account login
- Automatic publishing
- Comment or DM automation
- Large-scale account analytics
- ROI guarantees
- Unverified claims

## Repository Structure

```text
commercial-insight-agent/
├── README.md
├── docs/
│   ├── prd.md
│   ├── user_workflow.md
│   ├── storage_architecture.md
│   ├── security.md
│   ├── video_provider.md
│   └── ui_spec.md
├── prompts/
│   ├── system.md
│   ├── daily_research.md
│   ├── topic_scoring.md
│   ├── short_video_script.md
│   ├── article_outline.md
│   ├── infographic_structure.md
│   ├── weekly_digest.md
│   ├── material_analysis.md
│   └── knowledge_retrieval.md
├── knowledge/
│   ├── personal_background.md
│   ├── positioning.md
│   ├── service_packages.md
│   ├── content_boundaries.md
│   ├── material_library.md
│   └── opinion_bank.md
├── config/
│   ├── app.yaml
│   └── knowledge.yaml
├── scripts/
│   └── knowledge_check.py
├── skills/
│   ├── brief-router/
│   └── product-ui-guardrails/
└── data/
    ├── sources.yaml
    ├── insight_schema.yaml
    ├── material_schema.yaml
    ├── knowledge_note_schema.yaml
    ├── task_brief_schema.yaml
    ├── job_schema.yaml
    └── topic_schema.yaml
```

## Obsidian Knowledge Vault

The private Obsidian Vault lives in the sibling directory `../commercial-insight-vault`. The Agent repository contains only schemas, retrieval rules, and prompts; private source material and customer learning remain in the Vault.

Check local connectivity with:

```bash
python3 scripts/knowledge_check.py
```

See `docs/knowledge_architecture.md` for the hybrid retrieval and evaluation design.

## Founder Workspace Design

- `docs/user_workflow.md`: capture-to-export user flow
- `docs/storage_architecture.md`: Obsidian, SQLite, and local file responsibilities
- `docs/security.md`: GitHub sync and data classification rules
- `docs/video_provider.md`: MVP video boundary and future provider contract
- `docs/ui_spec.md`: local workbench information architecture and visual rules

## Primary Channels

- Douyin
- WeChat Video Account

## Manual Review Required

Before publishing, manually review:

- Factual accuracy
- Data sources
- Prior employer boundaries
- Sensitive company or individual references
- Overpromising or ROI claims
- Whether the final view represents the author's actual judgment
