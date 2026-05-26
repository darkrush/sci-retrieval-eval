# 0019. Retrieval Run Artifact

- Status: Accepted
- Date: 2026-05-27

## Context

The corpus build chain now produces auditable artifacts for raw data, normalized datasets, chunked corpus, embeddings, Elasticsearch indexes, and Milvus collections. Metrics should not query search systems directly; they need a stable retrieval result artifact that records what each query retrieved and how the run was configured.

The reference `sciverse_benchmark` Python runtime uses this flow:

```text
query
  -> optional rewrite
  -> Elasticsearch BM25 recall
  -> query embedding
  -> Milvus vector recall
  -> hybrid RRF fusion
  -> Elasticsearch enrichment
  -> optional rerank
  -> final topK
```

## Decision

Add a new artifact type:

```text
retrieval_run
```

Artifact layout:

```text
retrieval_run/<artifact_id>/
  results/part-00000.jsonl
  ...
  _MANIFEST.json
  _SUCCESS
```

Each JSONL row is one normalized query result:

- `query_id`
- `query_text`
- ordered `hits`
- optional `trace`
- optional `error`

Each hit keeps both `chunk_id` and `doc_id`. This is required because later metrics can rank chunks but aggregate relevance by document.

The runner supports three modes:

- `es`: Elasticsearch BM25 only.
- `milvus`: embedding + Milvus vector recall + Elasticsearch enrichment.
- `hybrid`: embedding + Milvus recall + Elasticsearch BM25 recall + RRF + Elasticsearch enrichment.

The runner uses injectable protocols:

- `ElasticsearchRetrievalClient`
- `MilvusRetrievalClient`
- existing `EmbeddingClient`
- `RewriteClient`
- `RerankClient`

This PR intentionally implements the artifact, protocol, fusion logic, and runner; it does not implement real Elasticsearch, Milvus, rewrite, or rerank network adapters.

## Algorithm Notes

RRF follows the reference runtime:

```text
score = sum(1 / (k + rank))
k = 60
sort = score desc, chunk_id asc
```

When the same `chunk_id` appears in both Milvus and Elasticsearch:

- `recall_source = "milvus|es"`
- `origin_milvus_score` records the vector score.
- `origin_es_score` records the BM25 score.

Rewrite handling:

- Keep the original query first.
- Strip blanks.
- Lowercase for dedupe.
- Drop rewrites equal to the original query.
- Cap total paths at `1 + sub_queries`.

Rerank handling:

- Candidate hits are sorted by `score desc, chunk_id asc`.
- `rerank_candidate_cap` limits the rerank head when positive.
- Reranked hits are followed by the non-reranked tail.

Per-query errors are written into that query result and counted in the manifest. Missing required clients is a configuration error and does not write `_SUCCESS`.

## Manifest

The manifest metadata records:

- source normalized dataset artifact id
- Elasticsearch index artifact id
- Milvus collection artifact id
- retrieval mode and topK
- query count and success/failure counts
- shard settings
- rewrite/rerank settings
- RRF and candidate-cap parameters
- result file and record counts

Dependencies include:

- `normalized_dataset`
- `elasticsearch_index` when ES or ES enrichment is required
- `milvus_collection` for Milvus or hybrid modes

## Consequences

Positive effects:

- Metrics can consume retrieval outputs without calling live retrieval services.
- Query-level failures are auditable without failing an entire run.
- Retrieval behavior can be tested with fake clients.

Tradeoffs:

- Real ES / Milvus / rewrite / rerank adapters remain future work.
- Trace output can be large, so it is opt-in via `include_trace`.

Non-goals:

- No metrics computation.
- No complete evaluation runner.
- No HTTP server or CLI.
- No real external service access in tests.
