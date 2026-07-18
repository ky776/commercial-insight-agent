# PRD: Personal Commercial Insight Agent

## 1. Goal

Build a lightweight research assistant that helps produce high-quality content for a content-led consulting business.

The agent should help discover signals, structure information, generate content ideas, and draft scripts. It should not publish content or replace human judgment.

The first product is a local-first founder workspace for one operator. It is not a customer self-service product.

## 2. Target Audience

The content is designed for:

- SMB brand owners
- Marketing and advertising leads
- Agency owners
- MCN and creator-commerce teams
- Content commerce service providers

## 3. Core Content Thesis

Many SMB brands spend money on ads, agencies, creators, and content, but the owner cannot clearly see:

- Where the budget is wasted
- Whether the agency is transparent
- Whether creator campaigns are measurable
- Whether leads and transactions are properly followed up
- Which reports and indicators actually matter

The content should translate ad platform and commercial system knowledge into practical owner-level judgment.

## 4. MVP Functions

### Input And Task Brief

Accept text, URLs, and local files. Create an editable structured brief before expensive analysis or generation.

Output:

- Goal and target audience
- Source references
- Constraints and deliverable
- Confirmed decisions and assumptions
- No more than three blocking questions
- Knowledge queries and context budget

### Daily Research

Collect and summarize recent information from selected industry sources.

Output:

- Key events
- Source and time
- Affected platforms or industries
- Business impact
- Content angles
- Follow-up questions

### Insight Structuring

Convert raw information into structured insight cards.

Output:

- Facts
- Uncertain points
- Affected groups
- Impact on brand owners, agencies, creators, and platforms
- Business implications

### Topic Generation

Generate content topics based on insight cards.

Output:

- Topic ideas
- Target audience
- Core pain point
- Core judgment
- Recommended format and platform
- Conversion path

### Topic Scoring

Score topics by:

- Owner pain intensity
- Professional differentiation
- Save/share potential
- Service conversion potential
- Evidence quality
- Risk level
- Sustainability

### Draft Generation

Generate drafts for:

- 60-90 second short video scripts
- WeChat article outlines
- Infographic structures
- Weekly digests
- Shot lists, captions, B-roll suggestions, and cover copy

## 5. Non-goals

The MVP does not:

- Log in to third-party platforms
- Store user credentials
- Publish automatically
- Auto-reply to comments or DMs
- Guarantee ROI
- Use unverified data as fact
- Generate complete videos
- Provide customer accounts, billing, or public sharing
- Store client raw data in GitHub

## 6. Workflow

The product workflow is defined in `docs/user_workflow.md`. The daily and weekly editorial routines below operate through the same job and artifact model.

### Daily

1. Collect recent signals.
2. Create insight cards.
3. Generate 5-10 topic ideas.
4. Score topics.
5. Pick 1-3 priority topics.
6. Draft one short video script.
7. Draft one article outline.
8. Mark facts requiring manual verification.

### Weekly

1. Summarize important industry changes.
2. Create a weekly digest.
3. Review published content performance manually.
4. Update the customer question library.
5. Plan next week's content calendar.

## 7. Success Metrics

### First 30 Days

- 30+ topic ideas
- 12 short videos published manually
- 4 long-form articles or outlines
- 5-10 meaningful conversations

### First 90 Days

- 30 qualified inbound messages
- 10 discovery calls
- 3 paid diagnostic projects
- 1 anonymized showcase

### First 180 Days

- 10-20 diagnostic customers
- 2-5 monthly advisory customers
- 3+ anonymized cases
- A clear decision on service-led cash flow vs. productization
