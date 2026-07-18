---
name: brief-router
description: Convert loose Chinese or English requests, links, notes, and attachments into compact executable briefs. Use when a user is exploring an idea, supplies mixed or lengthy context, asks for analysis or content generation, changes an existing request, or wants to reduce repeated clarification and model-context cost.
---

# Brief Router

Turn informal input into the smallest context packet that preserves intent and supports the next action.

## Personal Profile

When available, read the private profile at `${CODEX_HOME:-~/.codex}/brief-router/profile.yaml`. Apply only confirmed preferences relevant to the current request. Do not load raw conversation history.

Use `references/profile-policy.md` when proposing or saving a preference change.

## Workflow

1. Classify the request as `capture`, `discuss`, `decide`, or `execute`.
2. Extract the six core fields: goal, audience, inputs, constraints, deliverable, and open decisions.
3. Preserve file paths, URLs, quoted claims, dates, numbers, and explicit user wording exactly.
4. Mark assumptions instead of silently filling material gaps.
5. Ask at most three questions, and only when their answers would change the approach, cost, risk, or output.
6. Before expensive retrieval or generation, show a compact brief for correction.
7. On follow-up turns, update only changed fields and retain confirmed decisions.
8. Retrieve only the knowledge notes needed for this brief; never load the full Vault by default.

## Modes

- `capture`: Store the input quickly. Do not block on questions.
- `discuss`: Surface hypotheses, tradeoffs, and missing evidence. Do not pretend a decision exists.
- `decide`: Present the smallest useful option set, recommendation, and decision criteria.
- `execute`: Produce an implementation-ready brief and proceed after blocking gaps are resolved.

## Brief Output

Use this order:

```yaml
mode:
goal:
audience:
inputs: []
constraints: []
deliverable:
confirmed_decisions: []
assumptions: []
blocking_questions: []
knowledge_queries: []
file_scope: []
budget_profile: light | standard | deep
```

Keep the brief under 250 Chinese characters when possible, excluding paths and URLs. Use `light` for capture and formatting, `standard` for research and drafting, and `deep` only for high-impact strategy, architecture, or multi-source verification.

## Token Discipline

- Pass summaries and stable identifiers instead of entire previous conversations.
- Cache transcription, OCR, source extraction, and note chunking outputs.
- Use metadata filters before semantic retrieval.
- Start with 4-6 evidence chunks; expand only when evidence conflicts or is insufficient.
- Do not include unchanged fields in a delta update.
- Keep raw source material outside the prompt and reference it by path or source ID.
- Never trade away critical facts, user constraints, evidence, or uncertainty merely to reduce tokens.
- Do not silently learn or persist a preference. Ask for confirmation before changing the profile.

## Resources

- Read `references/brief-schema.md` when validating fields or building a UI form.
- Read `references/profile-policy.md` when adapting to repeated communication behavior.
- Run `scripts/brief_state.py` to merge a saved brief with a delta and estimate context size.
