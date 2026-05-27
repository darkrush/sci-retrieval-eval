# 开发报告

本文件由开发 session 维护。验收 session 默认只检查这里，不追聊天记录。

## 1. 任务信息

- 任务名：`benchmark suite / E1-E4 batch runner base`
- 当前分支：`feat/benchmark-suite-runner`
- 对应指令文件：`TASK.md`
- 开始时间：2026-05-27
- 完成时间：2026-05-27
- 实现提交 SHA：`b9aa6d6c7e7ca82d4226a786889013594203ca6f`
- 报告提交 SHA：本报告单独提交后由 `git log -1 --oneline` 确认；提交内容无法自引用自身 SHA。

## 2. 新增模块和职责

新增：

- `src/eval_platform/benchmark/settings.py`
  - `BenchmarkSettingSpec`
  - `DEFAULT_E1_E4_SETTINGS`
  - `settings_for_selection(...)`
- `src/eval_platform/benchmark/suite.py`
  - `BenchmarkDatasetSpec`
  - `BenchmarkSuiteRunConfig`
  - `BenchmarkSuiteItemSummary`
  - `BenchmarkSuiteRunSummary`
  - `build_benchmark_run_config(...)`
  - `run_benchmark_suite(...)`
- `src/eval_platform/benchmark/suite_artifact.py`
  - `write_benchmark_suite_run_artifact(...)`
  - `read_benchmark_suite_run_artifact(...)`
  - `BenchmarkSuiteArtifactError`

更新：

- `src/eval_platform/artifacts/types.py`
  - 新增 `BENCHMARK_SUITE_RUN_ARTIFACT_TYPE = "benchmark_suite_run"`。
- `src/eval_platform/artifacts/__init__.py`
  - 导出新增 artifact type。
- `src/eval_platform/benchmark/__init__.py`
  - 导出 suite runner、schema、artifact IO 和 E1-E4 registry。

## 3. E1-E4 setting 定义

`DEFAULT_E1_E4_SETTINGS` 顺序稳定：

```text
E1-milvus:
  retrieval_mode="milvus"
  sub_queries=0
  rewrite_enabled=False
  rerank_enabled=False

E2-es:
  retrieval_mode="es"
  sub_queries=0
  rewrite_enabled=False
  rerank_enabled=False

E3-hybrid:
  retrieval_mode="hybrid"
  sub_queries=0
  rewrite_enabled=False
  rerank_enabled=False

E4-hybrid-rerank:
  retrieval_mode="hybrid"
  sub_queries=0
  rewrite_enabled=False
  rerank_enabled=True
```

`settings_for_selection(...)` 支持：

- `None` / `"all"`：返回 E1-E4 全量顺序。
- 单个 key。
- key list，按输入顺序返回。
- 未知 key 抛 `ValueError`。

## 4. Suite artifact schema 摘要

新增 artifact type：

```text
benchmark_suite_run
```

artifact layout：

```text
benchmark_suite_run/<suite_run_id>/summary.json
benchmark_suite_run/<suite_run_id>/_MANIFEST.json
benchmark_suite_run/<suite_run_id>/_SUCCESS
```

`summary.json` 包含：

- `suite_run_id`
- `item_count`
- `dataset_count`
- `setting_count`
- `items`
  - `dataset_key`
  - `setting_key`
  - `benchmark_run_artifact_id`
  - `retrieval_run_artifact_id`
  - `metrics_run_artifact_id`
  - `main_score`
  - `main_score_metric`
  - `aggregate_metrics`

`summary.json` 不包含 query-level metrics，也不包含 retrieval hits。

manifest metadata 包含：

- `stage = "benchmark_suite_run"`
- `suite_run_id`
- `dataset_count`
- `setting_count`
- `item_count`
- `datasets` 的可审计输入摘要
- `settings` 的可审计输入摘要

manifest dependencies 当前只包含所有 child `benchmark_run` artifact。理由：child `benchmark_run` manifest 已继续记录 normalized / retrieval / metrics 依赖，suite 层保持聚合关系清晰，避免重复展开过多底层依赖。

## 5. Artifact id 生成规则

每个 dataset x setting item 的 id 稳定生成：

```text
<suite_run_id>__<dataset_key>__<setting_key>__retrieval
<suite_run_id>__<dataset_key>__<setting_key>__metrics
<suite_run_id>__<dataset_key>__<setting_key>__benchmark
```

key 校验：

- `suite_run_id` / `dataset_key` / `setting_key` 不允许为空。
- 只允许字母、数字、点、下划线、连字符。
- 重复 dataset key / setting key 抛错。
- 不做自动 sanitize，避免输入 key 和 artifact id 映射不透明。

## 6. run_benchmark_suite 复用方式

`run_benchmark_suite(...)` 不重新实现 retrieval 或 metrics。

执行流程：

1. 按 `datasets` 外层顺序、`settings` 内层顺序遍历。
2. 调用 `build_benchmark_run_config(...)` 生成现有 `BenchmarkRunConfig`。
3. 顺序调用既有 `run_benchmark(...)`。
4. 读取 child `benchmark_run` summary。
5. 聚合 `BenchmarkSuiteRunSummary`。
6. 所有 child 完成后才写 suite artifact 和 `_SUCCESS`。

失败行为：

- 如果 child benchmark 失败，不写 `benchmark_suite_run` success marker。
- 已完成的 child artifact 不回滚。

## 7. 对既有 public API 的影响

既有 public API 未改变：

- `run_benchmark(...)`
- `BenchmarkRunConfig`
- `BenchmarkRunSummary`
- retrieval / metrics / benchmark_run artifact schema

新增 public exports 仅追加 suite 相关入口，不改变原有 import。

## 8. 测试结果

已运行：

```bash
pytest tests/benchmark tests/artifacts/test_types.py
pytest
ruff check .
mypy .
```

结果：

- `pytest tests/benchmark tests/artifacts/test_types.py`
  - `24 passed in 0.22s`
- `pytest`
  - `596 passed in 2.22s`
- `ruff check .`
  - `All checks passed!`
- `mypy .`
  - `Success: no issues found in 171 source files`

## 9. 外部服务访问

- 是否访问真实 S3：`no`
- 是否访问真实 ES：`no`
- 是否访问真实 Milvus：`no`
- 是否访问真实 embedding：`no`
- 是否访问真实 rerank：`no`
- 是否访问真实 rewrite：`no`

本轮只使用本地 fake client 和本地 artifact store 测试。

## 10. 未实现项

按 `TASK.md` 要求，本轮未实现：

- CLI。
- E5/E6。
- rewrite setting。
- comparison report。
- 并发调度。
- 真实五数据集运行。
- 真实配置读取或真实外部服务接入。

## 11. 风险与未决项

- suite manifest dependencies 只记录 child `benchmark_run`，底层 normalized / retrieval / metrics 依赖通过 child manifest 追踪。
- 本轮没有实现真实五数据集 asset discovery；suite 输入要求显式提供 dataset asset spec。
- suite runner 当前顺序执行，后续并发调度需要单独设计失败语义和部分成功记录。

## 12. 交付结论

- 是否建议验收：`yes`
- 是否建议合并：`yes`
- 如果不能合并，卡点是什么：无
