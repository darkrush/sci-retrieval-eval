# 开发报告

本文件由开发 session 维护。验收 session 默认只检查这里，不追聊天记录。

## 1. 任务信息

- 任务名：`retrieval_run artifact`
- 当前分支：`feat/retrieval-run-artifact`
- 对应指令文件：`TASK.md`
- 开始时间：2026-05-27
- 完成时间：2026-05-27

## 2. 本次改动

- 新增 retrieval schema：
  - `RetrievalHit`
  - `RetrievalQueryResult`
- 新增 retrieval JSONL helper：
  - `dump_retrieval_results_jsonl(...)`
  - `load_retrieval_results_jsonl(...)`
- 新增 `retrieval_run` artifact IO：
  - `write_retrieval_run_artifact(...)`
  - `read_retrieval_run_artifact(...)`
  - 默认按 `results/part-xxxxx.jsonl` 分片写出
- 新增 retrieval client protocols：
  - `ElasticsearchRetrievalClient`
  - `MilvusRetrievalClient`
  - `RewriteClient`
  - `RerankClient`
- 新增 fusion helpers：
  - `rrf_fuse(...)`
  - `dedupe_sequential(...)`
  - `dedupe_by_chunk_id(...)`
- 新增 retrieval runner：
  - `RetrievalRunConfig`
  - `RetrievalRunError`
  - `run_retrieval(...)`
- 更新：
  - `src/eval_platform/retrieval/__init__.py`
  - `docs/decisions/0019-retrieval-run-artifact.md`
  - `docs/ai/current_status.md`
  - `report.md`
- 新增测试：
  - `tests/retrieval/test_fusion.py`
  - `tests/retrieval/test_artifact.py`
  - `tests/retrieval/test_runner.py`

## 3. Artifact 设计

新增 artifact type：

```text
retrieval_run
```

文件结构：

```text
retrieval_run/<artifact_id>/
  results/part-00000.jsonl
  results/part-00001.jsonl
  _MANIFEST.json
  _SUCCESS
```

每条 JSONL 记录对应一个 normalized query：

- `query_id`
- `query_text`
- `hits`
- `trace`
- `error`

每个 hit 保留：

- `rank`
- `chunk_id`
- `doc_id`
- `title`
- `text`
- `score`
- `recall_source`
- `origin_es_score`
- `origin_milvus_score`
- `metadata`

## 4. Manifest

manifest metadata 记录：

- `stage = retrieval_run`
- `source_normalized_dataset_artifact_id`
- `elasticsearch_index_artifact_id`
- `milvus_collection_artifact_id`
- `retrieval_mode`
- `top_k`
- `query_count`
- `succeeded_query_count`
- `failed_query_count`
- `queries_per_shard`
- `include_trace`
- `sub_queries`
- `rewrite_enabled`
- `rerank_enabled`
- `hybrid_per_source_topk`
- `rrf_path_topk`
- `rerank_cross_path_topk`
- `rerank_candidate_cap`
- `result_file_count`
- `result_record_count`

dependencies 记录：

- `normalized_dataset`
- `elasticsearch_index`，当 ES recall 或 ES enrich 需要时
- `milvus_collection`，当 `retrieval_mode in {"milvus", "hybrid"}` 时

## 5. 检索算法对齐

### 5.1 Retrieval Mode

- `es`
  - 调用 `es_client.search_bm25(index_name, query, top_k)`
- `milvus`
  - 调用 `embedding_client.embed_texts(...)`
  - 调用 `milvus_client.search(collection_name, vector, top_k)`
  - 调用 `es_client.enrich_by_chunk_ids(...)`
- `hybrid`
  - 调用 embedding / Milvus / ES
  - 使用 RRF 融合
  - 再调用 ES enrich

Milvus 模式也要求 ES client 和 `index_name`，因为需要 ES enrich 来拿完整 chunk text。

### 5.2 RRF

RRF 对齐 `sciverse_benchmark.search_runtime.fusion.rrf_fuse`：

```text
score = sum(1 / (k + rank))
k = 60
sort = score desc, chunk_id asc
```

同一 `chunk_id` 同时来自 Milvus 和 ES 时：

- `recall_source = "milvus|es"`
- `origin_milvus_score` 保留 Milvus 原始分数
- `origin_es_score` 保留 ES 原始分数

### 5.3 Rewrite

当 `rewrite_enabled=True and sub_queries > 0`：

- 原 query 保留在第一位
- rewrite query 去空白
- lowercase 去重
- 不保留与原 query 重复的 rewrite
- 最多 `1 + sub_queries` 条 query path
- 多 query path 下，Milvus/hybrid 会 batch 调用 `embed_texts(...)`

### 5.4 Rerank

当 `rerank_enabled=True`：

- 候选先按 `score desc, chunk_id asc` 排序
- `rerank_candidate_cap > 0` 时只 rerank head
- rerank 结果后拼接未 rerank tail
- 最终输出 `top_k`

## 6. 实现范围

已实现：

- artifact schema/read/write
- RRF / dedupe 算法
- runner orchestration
- fake-client unit tests
- query-level failure 记录
- include_trace 开关

未实现：

- 真实 Elasticsearch retrieval adapter
- 真实 Milvus retrieval adapter
- 真实 rewrite adapter
- 真实 rerank adapter
- metrics 计算
- evaluation runner
- CLI / HTTP server

## 7. 范围自检

- 是否改动流程控制文档：`no`
- 是否访问真实 ES / Milvus / embedding / rewrite / rerank 服务：`no`
- 是否实现 metrics：`no`
- 是否实现 evaluation runner：`no`
- 是否实现 HTTP server / CLI：`no`
- 是否修改 corpus build 主链路语义：`no`
- 是否修改 ES / Milvus ingest artifact 语义：`no`
- 是否提交 `.local_artifacts` 或真实 config / 密钥：`no`

## 8. 自检结果

### 8.1 已运行命令

```bash
pytest tests/retrieval
pytest tests/retrieval tests/embeddings tests/indexes
ruff check .
mypy .
pytest
```

### 8.2 输出摘要

- `pytest tests/retrieval`
  - 通过，`12 passed`
- `pytest tests/retrieval tests/embeddings tests/indexes`
  - 通过，`180 passed`
- `ruff check .`
  - 通过
- `mypy .`
  - 通过，`Success: no issues found in 117 source files`
- `pytest`
  - 通过，`481 passed`

## 9. 风险与未决项

- 本轮没有真实 ES / Milvus / rewrite / rerank adapter，因此真实联调仍需后续 PR。
- `trace` 可能较大，默认关闭；需要调试时通过 `include_trace=True` 打开。
- query-level error 当前写入 result artifact 并继续 run；后续 metrics 需要明确如何处理失败 query。
- 真实 adapter 接入时需要检查 ES BM25 字段权重 `title^1.5` / `text` 和 ES enrich 返回顺序。

## 10. 交付结论

- 是否建议验收：`yes`
- 是否建议合并：`yes`
- 如果不能合并，卡点是什么：无

## 11. 提交信息

- 是否已提交：`yes`
- commit subject：`Add retrieval run artifact`
- 验收者确认的最终 commit：
