# 开发报告

本文件由开发 session 维护。

验收 session 默认只检查这里，不追聊天记录。

## 1. 任务信息

- 任务名：embedding 一致性与 provenance 补强第一版
- 当前分支：`feat/embedding-consistency-hardening`
- 对应指令文件：`TASK.md`
- 开始时间：2026-05-26
- 完成时间：2026-05-26

## 2. 本次改动

- 改了什么：
  - 在 `src/eval_platform/embeddings/` 中新增多 endpoint 配置和一致性预检查能力。
  - 扩展 `EmbeddingProvenance` 与 `EmbeddingRunConfig`，显式记录 endpoint 集合、预检查结果和关键运行参数。
  - 为 schema、client 和 runner 补了对应测试。
- 为什么这样改：
  - 当前主线已经能产出 `embeddings` artifact，但还不能明确回答“多个 endpoint 是否可混用”以及“这次 embedding 到底用了哪个 endpoint / endpoint 集合”。
  - 本次补强让 embedding 阶段在进入 ES / Milvus ingest 之前，先具备更完整的一致性与 provenance 表达。
- 没改什么：
  - 没有实现真实外部一致性检查调用。
  - 没有实现 ES / Milvus builder。
  - 没有实现 retrieval pipeline。
  - 没有实现 metrics / report 生成逻辑。

## 3. 涉及文件

- `src/eval_platform/embeddings/__init__.py`
- `src/eval_platform/embeddings/client.py`
- `src/eval_platform/embeddings/runner.py`
- `src/eval_platform/embeddings/schema.py`
- `tests/embeddings/test_client.py`
- `tests/embeddings/test_runner.py`
- `tests/embeddings/test_schema.py`
- `docs/decisions/0010-embedding-consistency-hardening.md`
- `docs/ai/current_status.md`
- `report.md`

### 3.1 范围自检

- 是否改动了流程控制文档：`no`
- 如果是，改动理由：无

## 4. 实现说明

### 4.1 关键决策

- 决策 1：
  - 把多 endpoint 配置和一致性预检查放在 `embeddings/` 模块内，而不是提前扩到 index / retrieval。
- 决策 2：
  - 一致性规则默认使用 `max_abs_diff == 0.0` 的严格口径，但允许通过 `EmbeddingConsistencyTolerance.max_abs_diff` 显式声明容差。
- 决策 3：
  - 不新增真实网络逻辑，只通过 fake client / fake transport 在单元测试中验证一致 / 不一致分支。

### 4.2 关键行为

- 行为 1：
  - `MultiEndpointEmbeddingConfig` 能表达 endpoint 列表、是否要求一致性预检查、以及容差规则。
- 行为 2：
  - `run_embedding_consistency_check(...)` 会对同一输入文本调用多个 endpoint client，并返回结构化的 `EmbeddingConsistencyCheckResult`。
- 行为 3：
  - `run_embedding(...)` 现在可以把 endpoint 身份、预检查结果和关键运行参数写进 `EmbeddingProvenance`。

## 5. 自检结果

### 5.1 必跑命令

```bash
git status --short
git diff --name-only origin/main...HEAD
pytest tests/embeddings
ruff check .
mypy .
```

### 5.2 输出摘要

- `git status --short`：
  - 开发完成前仅包含本任务允许范围内文件改动。
- `git diff --name-only origin/main...HEAD`：
  - 仅涉及 `src/eval_platform/embeddings/`、`tests/embeddings/`、`docs/decisions/`、`docs/ai/current_status.md`、`report.md`。
- `pytest tests/embeddings`：
  - 通过，`92 passed`
- `pytest`：
  - 通过，`313 passed`
- `ruff check .`：
  - 通过
- `mypy .`：
  - 通过，`Success: no issues found in 78 source files`

### 5.3 提交信息

- 最新 commit：
  - 以当前分支最新 commit 为准
- 相关 commit 列表：
  - 本轮开发只提交当前任务相关 commit，不额外扩做其他功能

## 6. 风险与未决项

- 已知风险：
  - 当前一致性预检查只定义了 schema 和辅助函数，没有自动接入到真实 HTTP client 池调度流程。
- 未覆盖场景：
  - 没有覆盖真实外部 endpoint 的数值漂移统计，只覆盖 fake client 场景。
- 需要验收者重点检查的点：
  - `EmbeddingProvenance` 是否应该继续使用显式字段，而不是把 endpoint / precheck 信息全部放进 metadata。
  - `EmbeddingConsistencyTolerance.max_abs_diff` 作为唯一容差规则是否足够。

## 6.1 任务单中的疑点记录

- `TASK.md` 的完成标准第 1 条写的是：
  - `标准离线实验 schema 可以稳定构造`
- 这看起来像上一轮任务残留，不完全对应本轮 embedding consistency hardening。
- 本次开发未按该条扩做，只在 `report.md` 里留痕说明。

## 7. 交付结论

- 是否建议验收：`yes`
- 是否建议合并：`yes`
- 如果不能合并，卡点是什么：无
