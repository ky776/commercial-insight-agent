# Communication Profile Policy

## What To Store

Store only durable interaction preferences that improve future work, such as:

- Preferred language and answer structure
- Comfortable level of technical detail
- Maximum number of clarification questions
- Whether to lead with recommendations or alternatives
- Preferred working modes and output formats

## What Not To Store

Do not store raw conversations, credentials, client data, health or financial details, private identifiers, temporary emotions, or one-off task content.

## Update Rule

Propose one concise profile update when either condition is met:

1. The user explicitly corrects the interaction style or asks to remember a preference.
2. The same preference is observed in at least three separate tasks.

Show the exact field and old/new value. Save only after explicit confirmation. Record the reason and update date, not the underlying conversation.

## Conflict Rule

The current user request overrides the profile. A project-specific instruction overrides a global profile inside that project. Do not reinterpret a direct request merely to match an old preference.
