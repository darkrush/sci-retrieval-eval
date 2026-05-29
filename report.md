# 开发报告

本文件由开发 session 维护。验收 session 默认只检查这里，不追聊天记录。

## 1. 任务信息

- 任务名：`Track B / PR1 Asset Fingerprint Foundations`
- 当前分支：`feat/asset-fingerprint-spec`
- 对应指令文件：`TASK.md`
- 基线：已合入最新 `origin/main` / `e006ada Update README with architecture and benchmark results (#38)`
- 开始时间：2026-05-28
- 完成时间：2026-05-30
- 实现提交 SHA：`56a885450abf85e39d1646244864f16ed1b6fdb8`
- 报告提交 SHA：本报告单独提交后由 `git log -1 --oneline` 确认；提交内容无法自引用自身 SHA

## 2. 实现内容

PR1 只覆盖 fingerprint schema/helper/spec/docs/tests，不接入 artifact writer，不改变 planner 行为。

新增 / 更新：

- `src/eval_platform/assets/fingerprint.py`
  - `canonical_json_hash(...)`
  - `AssetFingerprint`
  - `build_asset_fingerprint(...)`
  - `assert_no_secret_keys(...)`
  - 8 类核心资产 component builders：
    - `raw_dataset`
    - `normalized_dataset`
    - `chunked_corpus`
    - `embeddings`
    - `elasticsearch_index`
    - `milvus_collection`
    - `retrieval_run`
    - `metrics_run`
- `tests/assets/test_fingerprint.py`
  - 覆盖 canonical hash、secret/operational key guard、schema validation、8 类 builder 字段、等价性变化和最小评测链路。
- `docs/decisions/0023-asset-fingerprint-spec.md`
  - 记录 PR1 最终 fingerprint 设计。
- `docs/architecture.md`
  - 更新资产身份与等价性总览。
- `docs/operations/experiment_variants.md`
  - 更新最小重算示例。

## 3. 核心字段

`raw_dataset`：

- `dataset_name`
- `raw_source_uri`
- `raw_format`
- `split`
- `file_fingerprints`

`normalized_dataset`：

- `raw_dataset_fingerprint`
- `normalizer_name`
- `normalizer_version`
- `schema_version`
- `normalizer_params`

`chunked_corpus`：

- `normalized_dataset_fingerprint`
- `chunker_source`
- `chunker_name`
- `source_git_remote_url`
- `git_commit`
- `chunker_entrypoint`
- `chunk_params`
- `schema_version`

`embeddings`：

- `chunked_corpus_fingerprint`
- `embedding_source`
- `model_name`
- `model_revision`
- `embedding_dim`
- `endpoint_alias`
- `api_version`
- `input_field`
- `call_params`
- `normalized`
- `storage_type`

`elasticsearch_index`：

- `chunked_corpus_fingerprint`
- `builder_source`
- `code_git_commit`
- `builder_entrypoint`
- `builder_params`
- `mapping`
- `settings`
- `ingest_params`

`milvus_collection`：

- `chunked_corpus_fingerprint`
- `embeddings_fingerprint`
- `builder_source`
- `code_git_commit`
- `builder_entrypoint`
- `builder_params`
- `schema`
- `metric_type`
- `index_type`
- `index_params`

`retrieval_run`：

- `normalized_dataset_fingerprint`
- `retrieval_mode`
- ES / Milvus index fingerprints
- `query_source`
- `query_embedding`
- `search_params`
- `rewrite`
- `rerank`
- `trace_mode`

`metrics_run`：

- `normalized_dataset_fingerprint`
- `retrieval_run_fingerprint`
- `metrics_source`
- `code_git_commit`
- `metrics_entrypoint`
- `metric_params`

## 4. Guard 语义

`canonical_json_hash(...)` 使用 canonical JSON：

```text
sort_keys=True
ensure_ascii=False
separators=(",", ":")
allow_nan=False
```

并且拒绝：

- 非 JSON-serializable value。
- 非 string dict key。
- secret-like key：`api_key`、`access_key`、`secret`、`password`、`token`、`authorization`。
- operational identity key：`run_id`、`artifact_id`、`created_at`、`created_by`。

`git_status` / dirty tree / commit reachable 属于构建前置校验和 manifest metadata，不进入 fingerprint。

ES URL、Milvus URI、index name、collection name 应记录在 artifact manifest metadata 中，方便访问已有物理资源，但不进入 fingerprint。

## 5. 最小评测集实际测试

`tests/assets/test_fingerprint.py::test_minimal_e4_eval_builds_core_fingerprints_and_runs_metrics`
构造了一个本地 tiny eval：

- 1 个 normalized dataset。
- fake ES BM25 recall。
- fake Milvus vector recall。
- hybrid RRF fusion。
- fake rerank。
- `trace_mode="replay"`。
- `run_metrics(...)` 计算 doc-level metrics。

该测试同时为一条完整链路构造 8 类核心资产 fingerprint，并验证：

- ES hits、Milvus hits、fused hits、rerank input、rerank hits、final hits 都写入 trace。
- 最终 retrieval result 命中 qrel doc。
- metrics main score 大于 0。
- `metrics_run` fingerprint 绑定 `retrieval_run_fingerprint`。

本测试不访问真实 ES、Milvus、embedding、rerank 或 rewrite 服务。

## 6. 验证结果

已运行：

```bash
PYTHONPATH=src pytest tests/assets/test_fingerprint.py
PYTHONPATH=src pytest
ruff check .
mypy .
```

结果：

- `PYTHONPATH=src pytest tests/assets/test_fingerprint.py`
  - `30 passed in 0.19s`
- `PYTHONPATH=src pytest`
  - `642 passed in 2.02s`
- `ruff check .`
  - `All checks passed!`
- `mypy .`
  - `Success: no issues found in 175 source files`

## 7. 外部服务访问

- 是否访问真实 S3：`no`
- 是否访问真实 ES：`no`
- 是否访问真实 Milvus：`no`
- 是否访问真实 embedding：`no`
- 是否访问真实 rerank：`no`
- 是否访问真实 rewrite：`no`

## 8. 未实现项

按 PR1 范围，本轮未实现：

- artifact writer 接入 `asset_fingerprint`。
- planner 行为变更。
- minimal rebuild planner。
- stage override。
- pinned artifacts。
- benchmark_run / benchmark_suite_run fingerprint。
- benchmark variant spec。
- 真实外部服务运行。

## 9. 后续建议

PR2：各 artifact writer / runner 将 `asset_fingerprint` 写入 manifest metadata。
PR3：reuse planner 增加 `complete + artifact_type + dependency-compatible chain + fingerprint match` 联合校验。
PR4：minimal rebuild planning、stage override、pinned artifacts 和 variant spec。
