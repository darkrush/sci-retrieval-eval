# 开发报告

本文件由开发 session 维护。验收 session 默认只检查这里，不追聊天记录。

## 1. 任务信息

- 任务名：`五数据集 raw normalizer 扩展`
- 当前分支：`feat/raw-normalizers-all-datasets`
- 对应指令文件：`TASK.md`
- 开始时间：2026-05-26
- 完成时间：2026-05-26

## 2. 本次改动

- 扩展 `src/eval_platform/datasets/raw_normalize.py`
  - 新增 `RawNormalizerSpec`
  - 新增 `RAW_NORMALIZER_SPECS`
  - 新增 `SUPPORTED_RAW_NORMALIZER_DATASET_NAMES`
  - 支持 `jsonl_tsv` raw 格式
  - 支持 `LitSearchRetrieval` 的 parquet raw 格式
  - 校验 unsupported dataset 和 normalizer mismatch
  - manifest metadata 增加 `raw_format` / `has_instructions`
- 更新 `src/eval_platform/corpus_build/runner.py`
  - `CorpusBuildConfig.dataset_name` 改为从 raw normalizer registry 取 allowlist
  - 不改变 runner 阶段顺序和 artifact id 串联方式
- 更新 `src/eval_platform/datasets/__init__.py`
  - 导出 raw normalizer registry 相关公共对象
- 扩展测试
  - `tests/datasets/test_raw_normalize.py`
  - `tests/corpus_build/test_runner.py`
- 新增 ADR
  - `docs/decisions/0018-raw-normalizers-all-datasets.md`
- 更新状态文档
  - `docs/ai/current_status.md`
  - `report.md`

## 3. 支持的数据集

| dataset_name | normalizer_name | raw_format | has_instructions |
| --- | --- | --- | --- |
| `IFIRNFCorpus` | `ifir_nfcorpus_raw_jsonl_tsv_v1` | `jsonl_tsv` | `true` |
| `IFIRScifact` | `ifir_scifact_raw_jsonl_tsv_v1` | `jsonl_tsv` | `true` |
| `NFCorpus` | `nfcorpus_raw_jsonl_tsv_v1` | `jsonl_tsv` | `false` |
| `SciFact` | `scifact_raw_jsonl_tsv_v1` | `jsonl_tsv` | `false` |
| `LitSearchRetrieval` | `litsearch_raw_parquet_v1` | `parquet` | `false` |

## 4. 实现说明

### 4.1 JSONL / TSV normalizer

适用于：

- `IFIRNFCorpus`
- `IFIRScifact`
- `NFCorpus`
- `SciFact`

读取文件：

- `corpus.jsonl`
- `queries.jsonl`
- `qrels/test.tsv`
- `instructions.jsonl`，仅 IFIR 系列启用

字段映射：

- `corpus._id` -> `CorpusRecord.doc_id`
- `corpus.title` -> `CorpusRecord.title`
- `corpus.text` -> `CorpusRecord.text`
- `queries._id` -> `QueryRecord.query_id`
- `queries.text` -> `QueryRecord.text`
- `qrels.query-id` -> `QrelRecord.query_id`
- `qrels.corpus-id` -> `QrelRecord.doc_id`
- `qrels.score` -> `QrelRecord.relevance`
- `instructions.instruction` -> `QueryRecord.metadata["instruction"]`

### 4.2 LitSearch parquet normalizer

适用于：

- `LitSearchRetrieval`

读取文件：

- `corpus.parquet`
- `queries.parquet`
- `qrels.parquet`

Parquet 依赖策略：

- 基础安装不新增强依赖。
- 运行 LitSearch parquet normalizer 时 lazy import。
- 优先尝试 `pandas.read_parquet(...)`。
- 如果不可用，再尝试 `pyarrow.parquet`。
- 如果两者都不可用，抛 `RawNormalizeError("pandas or pyarrow is required to normalize parquet raw datasets")`。
- 单元测试通过 monkeypatch parquet reader，不依赖真实 parquet 库。

### 4.3 Manifest metadata

`normalized_dataset` manifest 继续记录：

- `source`
- `task_name`
- `split`
- `normalizer_name`
- `raw_dataset_artifact_id`
- `raw_dataset_fingerprint`
- `raw_source_uri`
- `normalized_schema_version`

本轮新增：

- `raw_format`
- `has_instructions`

### 4.4 Progress

`raw_to_normalized` progress 保留并扩展：

- `jsonl_tsv` 数据集汇报 `corpus` / `queries` / `instructions` 可选 / `qrels`
- `parquet` 数据集汇报 `corpus` / `queries` / `qrels`
- 每个事件 metadata 包含 `kind`、`record_count`、`path`

### 4.5 Corpus build runner

`CorpusBuildConfig.dataset_name` 不再硬编码 `IFIRNFCorpus`。

当前 allowlist 来自：

```python
SUPPORTED_RAW_NORMALIZER_DATASET_NAMES
```

runner 仍然只负责按 artifact id 串联阶段，不复制 raw parsing 逻辑。

## 5. 范围自检

- 是否改动流程控制文档：`no`
- 是否访问真实 S3 / ES / Milvus / embedding API：`no`
- 是否修改 ES / Milvus ingest 语义：`no`
- 是否修改 embedding / chunking 语义：`no`
- 是否实现 retrieval / metrics / frontend：`no`
- 是否新增 CLI / scheduler：`no`
- 是否提交 `.local_artifacts` 或真实 config / 密钥：`no`

## 6. 自检结果

### 6.1 已运行命令

```bash
pytest tests/datasets/test_raw_normalize.py tests/corpus_build/test_runner.py
pytest tests/datasets tests/corpus_build
ruff check .
mypy .
pytest
```

### 6.2 输出摘要

- `pytest tests/datasets/test_raw_normalize.py tests/corpus_build/test_runner.py`
  - 通过，`39 passed`
- `pytest tests/datasets tests/corpus_build`
  - 通过，`85 passed`
- `ruff check .`
  - 通过
- `mypy .`
  - 通过，`Success: no issues found in 107 source files`
- `pytest`
  - 通过，`464 passed`

## 7. 风险与未决项

- 已知风险：
  - 本轮只做 fake raw opener / local unit tests，没有访问真实 S3 raw source。
  - LitSearch parquet 在真实运行时需要环境具备 `pandas` 或 `pyarrow`。
  - one-off scripts 仍保留为历史参考，未迁移或删除。
- 非目标：
  - 不做 CLI。
  - 不做 retrieval / metrics。
  - 不做真实完整五数据集 ingest smoke。
  - 不改 ES / Milvus / embedding / chunking 语义。
- 需要验收者重点检查：
  - 五个 dataset 是否都有明确 registry spec。
  - unsupported dataset 和 normalizer mismatch 是否拒绝。
  - LitSearch parquet lazy import 和错误处理是否清晰。
  - runner 是否只从 registry 放开 allowlist，没有复制 raw parsing。

## 8. 交付结论

- 是否建议验收：`yes`
- 是否建议合并：`yes`
- 如果不能合并，卡点是什么：无

## 9. 提交信息

- 是否已提交：`yes`
- commit subject：`Add raw normalizers for target datasets`
- 验收者确认的最终 commit：
