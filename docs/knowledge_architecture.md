# Obsidian Knowledge Architecture

## Boundary

The public Agent repository stores prompts, schemas, retrieval rules, and code. The Obsidian Vault stores private notes, source material, client-related learning, and unpublished opinions. The Vault should use a separate private GitHub repository.

## Retrieval Pipeline

1. Parse Markdown, YAML frontmatter, headings, tags, and Obsidian links.
2. Filter by note type, topic, date, source, confidence, and publication status.
3. Retrieve candidates using both lexical search and multilingual embeddings.
4. Merge lexical and vector rankings with reciprocal rank fusion.
5. Rerank candidates with a multilingual cross-encoder or capable reasoning model.
6. Expand context through linked source and insight notes.
7. Generate an answer that separates fact, inference, opinion, and uncertainty.
8. Return exact note paths so every conclusion can be audited in Obsidian.

## Recommended Mature Components

- Parsing and orchestration: LlamaIndex or LangChain
- Local full-text search: SQLite FTS5 or Tantivy
- Vector storage for MVP: Qdrant local mode or LanceDB
- Multilingual embeddings: a current Chinese-English embedding model selected at implementation time
- Reranking: a current multilingual reranker selected at implementation time
- Reasoning: a capable reasoning model with structured output and citation constraints

Model names are intentionally kept out of repository defaults because model quality, price, and availability change. Selection should be benchmarked on the Vault's own Chinese advertising and commercialization questions.

## Evaluation Set

Maintain 20-50 representative questions covering:

- Advertising cost increases and optimization boundaries
- Platform traffic allocation changes
- Enterprise-owned content and brand assets
- Agency transparency and attribution
- Creator campaigns and commercial deal fulfillment
- Local services, ecommerce, short drama, and micro-drama

For each question, record expected source notes, required facts, unacceptable hallucinations, and a usefulness score. Do not upgrade retrieval models without rerunning this set.

## MVP Stages

### Stage 1: File access

Validate the Vault path, count Markdown notes, parse frontmatter, and report malformed notes.

### Stage 2: Search

Add full-text retrieval and metadata filters. This is sufficient while the Vault contains fewer than several hundred notes.

### Stage 3: Hybrid retrieval

Add embeddings, rank fusion, reranking, linked-note expansion, and an evaluation suite.

### Stage 4: Content workflow

Use retrieved notes to produce a daily report, topic scores, short video scripts, WeChat article outlines, and weekly reviews. Publication always remains manual.
