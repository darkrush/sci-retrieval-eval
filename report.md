# 开发报告

本文件由开发 session 维护。验收 session 默认只检查这里，不追聊天记录。

## 1. 任务信息

- 任务名：`严化 recall@inf incomplete artifact 行为`
- 当前分支：`fix/recall-inf-incomplete-artifact`
- 基线：`origin/main` / `3c9fcc9 Document experiment audit policy (#53)`
- 完成时间：2026-06-09
- 实现提交 SHA：待提交后补充
- 报告校正提交 SHA：待提交后补充

## 2. 实现摘要

- 在 `eval_platform.analysis.recall_inf` 中新增 `RecallInfAnalysisError`。
- `compute_recall_inf_metrics(...)` 读取 retrieval results 前会检查 `retrieval_run`
  artifact 是否 complete。
- 当 `retrieval_run` artifact 不存在、缺少 `_MANIFEST.json` 或缺少 `_SUCCESS` 时，
  recall@inf analysis 显式失败，不再把 retrieval 结果当作空集合并产出 0 recall。
- `experiment_run` 汇总复用已有 benchmark 时，如果 child `retrieval_run` artifact 已不可用，
  上层不追加 recall@inf diagnostic metrics，表示该诊断 unavailable；非 benchmark reuse
  路径仍会继续抛出 `RecallInfAnalysisError`。
- 保持 recall@inf 公式、trace schema、experiment schema、retrieval runner、
  metrics runner 和 planner 行为不变。

## 3. 测试更新

更新：

- `tests/analysis/test_recall_inf.py`
  - 覆盖 complete normalized dataset + 不存在的 retrieval_run artifact。
  - 覆盖 complete normalized dataset + retrieval_run manifest 存在但无 `_SUCCESS`。
  - 保留既有 complete retrieval_run 的 recall@inf 行为测试。

## 4. 文档更新

更新：

- `docs/operations/experiment_audit_policy.md`
  - 明确缺失或 incomplete 的 `retrieval_run` artifact 不能被解释为 0 recall。
  - 这类情况必须显式失败，或由上层报告标记为 unavailable。

## 5. 验证结果

已运行：

```bash
env PYTHONPATH=src pytest tests/analysis/test_recall_inf.py tests/experiments/test_runner.py
env PYTHONPATH=src pytest
ruff check .
mypy .
```

结果：

- `env PYTHONPATH=src pytest tests/analysis/test_recall_inf.py tests/experiments/test_runner.py`
  - passed，47 passed
- `env PYTHONPATH=src pytest`
  - passed，770 passed
- `ruff check .`
  - passed
- `mypy .`
  - passed

## 6. 外部服务访问

- 是否访问真实 S3：`no`
- 是否访问真实 ES：`no`
- 是否访问真实 Milvus：`no`
- 是否访问真实 embedding：`no`
- 是否访问真实 rerank：`no`
- 是否访问真实 rewrite：`no`
