# Founder Workspace UI Specification

## Product Character

Build a quiet, compact editorial workbench for repeated professional use. The interface should feel closer to a research and editing tool than a chatbot or marketing dashboard.

## Information Architecture

### Left Rail

- Inbox
- Active jobs
- Content drafts
- Knowledge
- Exports
- Settings

### Main Workspace

Show one job with a fixed step header:

```text
素材 -> 解析 -> 简报 -> 洞见 -> 生成 -> 审核 -> 导出
```

The main area contains the active source, brief, or artifact editor.

### Evidence Panel

The right panel shows source files, Obsidian citations, unresolved facts, privacy class, and generation history. It can collapse on smaller screens.

## Interaction Rules

- Support drag-and-drop, file selection, URL paste, and direct text capture.
- Always show job state, progress, failure reason, and next action.
- Let the user edit the brief before model work begins.
- Support selected-text revision and single-section regeneration.
- Show changes between versions before replacing the active draft.
- Keep human approval explicit for facts, final wording, and export.

## Visual Rules

- Use neutral white and gray surfaces with restrained green and red status accents.
- Avoid purple gradients, glowing decoration, oversized headings, and decorative dashboards.
- Use full-width work areas rather than nested cards.
- Use compact typography, 8px-or-less corner radii, and stable control sizes.
- Use Lucide icons for familiar commands and text labels for primary actions.
- Use tables and lists for jobs and sources; reserve cards for repeated artifacts only.
- Keep evidence visible near generated claims.

## Implementation Reference

Use shadcn/ui for editable component source and Radix primitives for accessible interaction behavior. Create a project-specific component preset instead of shipping their default visual treatment unchanged.

- https://ui.shadcn.com/docs
- https://www.radix-ui.com/primitives/docs/overview/introduction

## First Prototype Screens

1. Inbox and new-job drawer
2. Job workspace with brief editor
3. Generated script editor with evidence panel
4. Export history

Do not build account management, billing, customer login, or public sharing in the first prototype.
