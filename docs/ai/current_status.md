# Current Status

## Current Phase

Artifact store (in progress).

## Implemented

- Project rules (`AGENTS.md`)
- Architecture and AI collaboration docs (`docs/`)
- Package skeleton under `src/eval_platform/`
- CLI entry point: `evalctl version`
- Dev tooling: pytest, ruff, mypy (configured in `pyproject.toml`)
- Artifact manifest schema (`ArtifactManifest`, `ArtifactFile`, `ArtifactDependency`)
- Artifact store abstract interface (`ArtifactStore`)
- Local artifact store (`LocalArtifactStore`)

## In Progress

- Artifact store tests and documentation polish

## Not Implemented

- S3 artifact backend
- Dataset adapter
- Chunking pipeline
- Embedding pipeline
- ES/Milvus index builder
- Retrieval pipeline
- MTEB adapter
- Metrics and reports
- Frontend dashboard

## Current Risks

- AI agents may create unmaintainable scripts if project rules are not strict.
- MTEB doc-level evaluation and internal chunk-level evidence evaluation need to be clearly separated.
- Artifact versioning and manifest schema may evolve as pipelines are implemented.

## Next Task

Add S3 artifact backend and checksum validation helpers.
