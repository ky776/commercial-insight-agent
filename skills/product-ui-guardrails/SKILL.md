---
name: product-ui-guardrails
description: Design and review the founder-facing commercial insight workspace as a restrained, compact professional tool. Use when creating layouts, components, visual styles, interaction flows, responsive behavior, or frontend code for this project, especially when avoiding generic AI-chat and decorative dashboard patterns.
---

# Product UI Guardrails

Build an editorial workbench that makes sources, decisions, generated artifacts, and next actions easy to inspect.

## Product Shape

- Design for one founder performing repeated research and content-production work.
- Center every screen on a visible job, source, brief, artifact, or export.
- Use the fixed workflow: 素材, 解析, 简报, 洞见, 生成, 审核, 导出.
- Keep chat subordinate to direct editing and scoped revision controls.
- Keep evidence, uncertainty, privacy class, and version history near generated claims.

## Visual System

- Use white and neutral gray surfaces with restrained green success and red risk accents.
- Avoid purple gradients, glowing decoration, oversized headings, floating section cards, and fake analytics.
- Prefer full-width work areas, lists, tables, split panes, tabs, and side panels.
- Keep corner radii at 8px or less unless an existing component requires otherwise.
- Use stable dimensions for toolbars, step indicators, controls, and evidence panels.
- Use Lucide icons for familiar actions and pair unfamiliar icons with tooltips.
- Preserve compact readable typography without viewport-scaled font sizes or negative letter spacing.

## Interaction Rules

- Support drag-and-drop, file selection, URL paste, and direct text capture.
- Always expose current status, progress, error reason, and next action.
- Let the user edit the brief before expensive generation begins.
- Permit selected-text rewrite and single-section regeneration.
- Show a version diff before replacing an approved artifact.
- Require explicit approval for factual claims, export, and any external upload of restricted data.

## Review

Read `references/review-checklist.md` before finalizing a frontend implementation or visual review. Report violations by severity and fix blocking issues before presentation.
