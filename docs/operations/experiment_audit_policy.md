# Experiment Audit Policy

本文档是实验运行、比较和审计的操作口径。它不定义新功能，也不改变默认值；它把当前
主线已经实现的实验身份、trace、fingerprint、PAPER_CAP、IFIR policy 和 recall@inf
规则集中到一处，方便研发同事判断一次实验是否可比较、可复现、可排查。

## 1. Sciverse Benchmark V1 默认口径

当前主线默认实验口径如下。跨 commit、跨集群、跨真实服务环境比较时，必须逐项核对：

| 项 | 当前默认 |
| --- | --- |
| retrieval `top_k` | `100` |
| metrics `k_values` | `[5, 10, 20]` |
| `main_score_metric` | `recall_at_10` |
| `rerank_candidate_cap` | `0` |
| `paper_cap` | `0` |
| Milvus index | `HNSW + COSINE + M=16 + efConstruction=200` |
| Milvus search params | `{"metric_type": "COSINE", "params": {}}` |
| Milvus `title.max_length` | `65535` |
| Milvus `text.max_length` | `65535` |
| embedding dim | 不作为平台默认值，来自 embedding manifest 或显式配置 |

这些值会影响 baseline 结果。实验报告至少应记录 dataset selection、E1-E4 setting、
retrieval top-k、hybrid/RRF/rerank 参数、metric cutoff、Milvus schema/index/search 参数、
embedding/rerank endpoint alias 或对应 artifact identity。

## 2. Trace Mode Policy

`trace_mode` 决定 retrieval artifact 的可诊断能力和存储成本。

| trace mode | 建议用途 | 审计影响 |
| --- | --- | --- |
| `replay` | diagnostic run、需要逐 query 排查或复现的 baseline | 记录 ES hits、Milvus hits、fusion、rerank input/output 和 final hits，诊断能力最强 |
| `light` | large baseline run | 节省空间，但降低逐 query 归因能力 |
| `none` | low-storage exploratory run | 不适合需要 query-level attribution 的实验 |

建议：

- diagnostic run 应使用 `trace_mode=replay`。
- large baseline run 可使用 `trace_mode=light`，但报告必须写明诊断能力下降。
- metrics run 可以不读取 trace payload；这不等于 retrieval artifact 没有 trace。
- `trace_mode=none` 只适合低存储、不可诊断 run，不应用于需要逐 query attribution、
  recall@inf 解释或 replay 证据的实验。

Trace mode 通常不应改变 ranking 结果，但会改变可诊断性、replay 证据和 fingerprint
身份。因此比较实验时必须标注 trace mode。

## 3. Fingerprint / Reuse Policy

Artifact id、`run_id`、ES index name、Milvus collection name 是物理或运行身份，不是逻辑
资产身份。逻辑等价由 manifest 中的 `asset_fingerprint_sha256` 判断。

复用一个 artifact 至少需要满足：

- artifact type 匹配。
- manifest 和 `_SUCCESS` 存在。
- dependency chain 与当前需要的上游链路兼容。
- `asset_fingerprint_sha256` 匹配。

当前 fingerprint 是保守策略。部分 stage 会把 `code_git_commit` 作为 identity 组件，因此
commit 变化可能导致不复用，即使人工看起来语义没变。这是审计安全优先的选择：系统先
避免误复用。如果后续发现复用率过低，再引入 semantic builder version 或更细粒度的
兼容声明。

Catalog 是查询加速索引，不是唯一真相。最终证据仍是 artifact 目录中的 manifest、
dependencies、fingerprint 和 `_SUCCESS`。

## 4. 什么变化会产生新 Baseline

以下变化通常意味着实验结果不能直接和旧 baseline 混在一起比较，必须形成新 baseline
或至少在报告中单独标注：

- raw data 文件、qrels、split 或 raw snapshot fingerprint 变化。
- normalizer、normalized schema 或 IFIR query policy 变化。
- chunk params、chunk schema、external chunker repo / commit / entrypoint 变化。
- embedding model、model revision、provider、endpoint alias、dimension、API version、
  call params 或输入字段变化。
- ES mapping、settings/analyzer、ingest params 或 builder code identity 变化。
- Milvus schema、metric、index type、index params、builder code identity 变化。
- Milvus search params 变化。
- retrieval `top_k`、per-source top-k、RRF path top-k、final top-k 变化。
- rerank model、endpoint alias、rerank input/output top-k、rerank params 变化。
- `paper_cap` 变化。
- metric `k_values`、`main_score_metric`、projection policy 或 missing-query policy 变化。
- trace mode 变化：通常不应改变 ranking，但会影响诊断能力、fingerprint 和 replay 证据。

跨集群比较还应额外记录 ES/OpenSearch 版本、Milvus server 版本、client 版本、embedding
/ rerank 服务别名和真实 endpoint 对应关系。真实服务地址和凭证不进入 fingerprint，但
它们属于实验环境审计信息。

## 5. PAPER_CAP 解释边界

`paper_cap=0` 表示不启用额外 per-paper cap。

PAPER_CAP 会改变 hybrid candidate、rerank input 和 final ranking，因此必须进入
fingerprint。比较引入 PAPER_CAP 前后的实验时，必须显式标注 `paper_cap`。如果旧实验
没有记录该字段，不应默认把它和 `paper_cap=0` 的新实验视为完全同一口径，除非能从
代码版本和运行配置证明当时确实未启用。

## 6. IFIR Effective Query Policy

IFIR 不是普通 SciFact / NFCorpus query 集。它是 instruction-following retrieval：
query text、instruction 和 qrels 必须按 IFIR 任务定义一起理解。

当前主线对 MTEB IFIR 默认使用：

```text
mteb_text_plus_instruction
```

即：

```text
effective_query_text = query_text + " " + instruction
```

MTEB pinned 数据中 instruction 可能已经以 query text 开头，因此 effective query 可能
出现 query 文本重复一次。这是可复现口径，不自动去重。

IFIR normalized query text 改变会导致 downstream retrieval、metrics 和相关 artifact
fingerprint 变化，这是预期行为。详细设计见
[`docs/decisions/0024-ifir-effective-query-policy.md`](../decisions/0024-ifir-effective-query-policy.md)。

## 7. Recall@inf 解释边界

`recall@inf` 是 diagnostic metric，不是最终 leaderboard 主指标。默认主指标仍是
`recall_at_10`。

`recall@inf` 用于判断候选召回阶段是否拿到了正例，帮助区分两类问题：

- 召回阶段没有拿到正例。
- 召回拿到了正例，但 fusion、paper cap、rerank 或 final ranking 没排上去。

当前计算来源是 retrieval trace / final hits 中的 doc id 集，doc id fallback 顺序为：

```text
doc_id -> metadata.paper_id -> chunk_id
```

该诊断逻辑由 `eval_platform.analysis.recall_inf` 计算，并合并到 experiment item summary。
如果 trace mode 过轻或为 `none`，recall@inf 解释能力会下降，尤其难以区分 ES、Milvus、
fusion 和 rerank 的贡献。
缺失或 incomplete 的 `retrieval_run` artifact 不能被解释为 0 recall；这类情况必须显式失败，
或由上层报告标记为 unavailable。

## 8. 推荐运行矩阵

| 场景 | trace_mode | reuse_existing | metrics | 用途 |
| --- | --- | --- | --- | --- |
| smoke run | `light` 或 `replay` | `false` 或小范围 `true` | `[5, 10, 20]` | 快速验证配置、artifact 写入和服务连通路径 |
| full baseline run | `light` | `true` | `[5, 10, 20]`，主指标 `recall_at_10` | 生成可比较的常规 baseline，控制存储成本 |
| diagnostic run | `replay` | 视问题而定 | `[5, 10, 20]` + recall@inf diagnostics | 逐 query 排查召回、fusion、rerank、paper cap 问题 |
| low-storage exploratory run | `none` | `true` | 只保留必要 cutoff | 探索配置方向，不用于正式 attribution |
| cross-cluster reproduction run | `replay` 或 `light` | `true`，但必须校验 fingerprint | `[5, 10, 20]`，必要时补历史 cutoff | 比较不同集群、服务版本或物理环境差异 |

推荐报告 checklist：

- 记录 git commit、config 摘要、dataset selection 和 setting。
- 记录每个 stage 的 artifact id、fingerprint、dependencies 和 reuse/create action。
- 记录 trace mode、paper cap、IFIR policy、metric cutoff、main score metric。
- 记录 ES/Milvus/embedding/rerank 的逻辑 alias 和必要的物理环境版本。
- 对任何不能直接比较的变化，明确标注为新 baseline 或 diagnostic-only run。
