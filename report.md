# 开发报告

本文件由开发 session 维护。验收 session 默认只检查这里，不追聊天记录。

## 1. 任务信息

- 任务名：`补充 experiment audit policy 文档`
- 当前分支：`docs/experiment-audit-policy`
- 基线：`origin/main` / `d9e6fec Move recall@inf diagnostics to analysis (#52)`
- 完成时间：2026-06-09
- 实现提交 SHA：`312aa1c Document experiment audit policy`
- 报告校正提交 SHA：本报告校正提交后由 `git log -1 --oneline` 确认；提交内容无法自引用自身 SHA

## 2. 新增 / 更新文档

新增：

- `docs/operations/experiment_audit_policy.md`

更新：

- `README.md`
  - 在 Experiment 运行层补充 experiment audit policy 入口链接。
- `docs/architecture.md`
  - 在评测语义和文档结构中补充 experiment audit policy 入口链接。

## 3. 内容摘要

`experiment_audit_policy.md` 覆盖：

- Sciverse benchmark v1 默认口径 checklist。
- `trace_mode=replay/light/none` 的适用场景和诊断影响。
- fingerprint / reuse policy，以及 code commit 进入 fingerprint 的保守审计策略。
- 哪些变化会产生新 baseline。
- PAPER_CAP 的解释边界。
- IFIR effective query policy 的简要说明和 ADR 链接。
- recall@inf 的 diagnostic 语义和解释边界。
- smoke / full baseline / diagnostic / low-storage / cross-cluster reproduction 的推荐运行矩阵。

## 4. 是否改代码

否。

本轮只改文档和 `report.md`，没有修改代码、默认值、CLI、artifact schema、retrieval runner 或 metrics runner。

## 5. 验证结果

已运行：

```bash
git diff --check
test -f docs/operations/experiment_audit_policy.md
test -f docs/decisions/0024-ifir-effective-query-policy.md
```

结果：

- `git diff --check`
  - passed
- `test -f docs/operations/experiment_audit_policy.md`
  - passed
- `test -f docs/decisions/0024-ifir-effective-query-policy.md`
  - passed

## 6. 外部服务访问

- 是否访问真实 S3：`no`
- 是否访问真实 ES：`no`
- 是否访问真实 Milvus：`no`
- 是否访问真实 embedding：`no`
- 是否访问真实 rerank：`no`
- 是否访问真实 rewrite：`no`
