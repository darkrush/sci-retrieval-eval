# Current Status

## Current Phase

Embedding schema and artifact read/write completed locally and pending PR / merge review.

## Implemented

- Project rules (`AGENTS.md`)
- Architecture and AI collaboration docs (`docs/`)
- Local artifact store (`LocalArtifactStore`)
- S3 artifact store (`S3ArtifactStore`)
- Normalized dataset schema and artifact read/write
- MTEB per-dataset normalizer registry
- Chunked corpus schema and artifact read/write
- Chunking runner with version-pinned external Sciverse chunker adapter
- Embedding schema:
  - `EmbeddingProvenance`
  - `EmbeddingRecord`
  - `EmbeddedCorpus`
- Embeddings JSONL helpers
- Embeddings artifact read/write with dimension validation and source dependency metadata

## In Progress

- PR / merge review for `feat/embedding-schema`

## Not Implemented

- Real embedding API client
- Embedding runner / batching / retry
- ES/Milvus index builder
- Retrieval pipeline
- Metrics and reports
- Frontend dashboard

## Current Risks

- JSONL is simple and portable, but may not be the final storage format for large-scale embeddings.
- Embedding provenance is fixed now, but provider-specific metadata may need to expand in later PRs.

## Next Task

Open and merge `feat/embedding-schema`, then start `feat/embedding-runner`.
