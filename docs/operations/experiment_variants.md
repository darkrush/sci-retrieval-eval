# Experiment Variants and Asset Reuse

本文档记录后续实验变体规划的资产复用原则。当前实现只提供
`asset_fingerprint` 基础设施，不改变既有 planner 行为，也不接真实服务。

## 1. Identity Boundary

`run_id` 是一次构建或实验运行的操作性身份，可以继续出现在 artifact id、ES index
name、Milvus collection name 中。它不应进入资产 fingerprint，也不应作为判断两个资产
是否逻辑等价的依据。

资产逻辑身份由 `asset_fingerprint` 表示。fingerprint 只包含影响资产内容或行为的稳定
components，例如上游资产 fingerprint、dataset、normalizer、chunker commit、chunk
params、embedding model、index schema、retrieval params 和 metric params。

## 2. Reuse Checks

复用已有 artifact 时，后续 planner 至少应同时检查：

- artifact complete marker 存在。
- artifact type 与当前 stage 匹配。
- artifact dependency chain 与当前需要的上游链路兼容。
- artifact manifest 中的 `asset_fingerprint` 与当前需要的 fingerprint 匹配。

dependency chain 只证明 lineage，不能单独证明等价。artifact id 只定位物理产物，不能单独
证明等价。

## 3. Minimal Rebuild Examples

只改变 embedding model：

```text
reuse raw_dataset
reuse normalized_dataset
reuse chunked_corpus
reuse elasticsearch_index
rebuild embeddings
rebuild milvus_collection
rerun retrieval_run
rerun metrics_run
rerun benchmark_run / benchmark_suite_run
```

只改变 chunk params：

```text
reuse raw_dataset
reuse normalized_dataset
rebuild chunked_corpus
rebuild embeddings
rebuild elasticsearch_index
rebuild milvus_collection
rerun retrieval_run
rerun metrics_run
rerun benchmark_run / benchmark_suite_run
```

只改变 rerank 配置：

```text
reuse raw_dataset
reuse normalized_dataset
reuse chunked_corpus
reuse embeddings
reuse elasticsearch_index
reuse milvus_collection
rerun retrieval_run
rerun metrics_run
rerun benchmark_run / benchmark_suite_run
```

只改变 metric params：

```text
reuse raw_dataset
reuse normalized_dataset
reuse chunked_corpus
reuse embeddings
reuse elasticsearch_index
reuse milvus_collection
reuse retrieval_run
rerun metrics_run
rerun benchmark_run / benchmark_suite_run
```

## 4. Future Planner Inputs

后续 Track B2 / B3 可以在不改变 fingerprint 语义的前提下增加：

- stage override，例如强制重建某些 stage。
- pinned artifact，例如显式指定某个 artifact id，但仍需要校验 type、complete、dependency
  和 fingerprint。
- variant spec，例如同一 dataset 下多组 embedding、chunk、retrieval、rerank 或 metric
  参数矩阵。

这些能力不在当前 B1 范围内实现。
