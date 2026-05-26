# 开发报告

本文件由开发 session 维护。

验收 session 默认只检查这里，不追聊天记录。

## 1. 任务信息

- 任务名：新增 raw_dataset artifact
- 当前分支：`feat/raw-dataset-artifact`
- 对应指令文件：`TASK.md`
- 开始时间：2026-05-26
- 完成时间：2026-05-26

## 2. 本次改动

- 改了什么：
  - 新增 `src/eval_platform/datasets/raw.py`，定义 `raw_dataset` artifact 的 schema、manifest 字段和读写逻辑。
  - 新增 `src/eval_platform/datasets/raw_import.py`，支持：
    - 从本地目录导入 raw 文件快照
    - 从既有 S3 prefix 导入 raw 文件快照
  - 更新 `src/eval_platform/datasets/__init__.py`，导出 `raw_dataset` 相关公共接口。
  - 新增 `tests/datasets/test_raw_dataset.py`，覆盖 local store、本地目录导入、fake S3 source 导入和 fake S3 output 场景。
  - 新增 ADR `docs/decisions/0011-raw-dataset-artifact.md`。
- 为什么这样改：
  - 当前 `normalized_dataset` 直接从内存对象开始，缺少“原始输入先落盘”的可审计层。
  - `raw_dataset` artifact 先固定原始文件身份，后续才能稳定建立 `raw_dataset -> normalized_dataset` 依赖。
- 没改什么：
  - 没有实现 `raw_dataset -> normalized_dataset` 自动转换。
  - 没有实现 chunk / embedding / ES / Milvus / retrieval / metrics。
  - 没有访问真实外部服务或真实 S3。

## 3. 涉及文件

- `src/eval_platform/datasets/__init__.py`
- `src/eval_platform/datasets/raw.py`
- `src/eval_platform/datasets/raw_import.py`
- `tests/datasets/test_raw_dataset.py`
- `docs/decisions/0011-raw-dataset-artifact.md`
- `docs/ai/current_status.md`
- `report.md`

### 3.1 范围自检

- 是否改动了流程控制文档：`no`
- 如果是，改动理由：无

## 4. 实现说明

### 4.1 关键决策

- 决策 1：
  - `raw_dataset` 放在 `datasets/` 下，而不是 `artifacts/` 下。
  - 理由是这层仍属于“数据输入身份”，和 `normalized_dataset` 属于同一数据域。
- 决策 2：
  - artifact 内部原始文件统一写到 `files/` 子目录，避免与 `_MANIFEST.json`、`_SUCCESS` 混用命名空间。
- 决策 3：
  - manifest metadata 中的系统字段统一由写入逻辑最后覆盖，避免用户 metadata 覆盖 `stage / file_count / content_fingerprint_sha256` 等关键信息。

### 4.2 关键行为

- 行为 1：
  - `raw_dataset` manifest metadata 至少包含：
    - `stage`
    - `source_type`
    - `source_uri`
    - `dataset_name`
    - `dataset_revision`
    - `file_count`
    - `total_size_bytes`
    - `files`
    - `content_fingerprint_sha256`
    - `import_parameters`
- 行为 2：
  - 单文件 `sha256` 通过流式读取计算：
    - 按固定 chunk 大小逐块 `read(...)`
    - 每块增量更新 `hashlib.sha256()`
    - 不在 hash 阶段一次性整文件读入内存
- 行为 3：
  - dataset 级 `content_fingerprint_sha256` 按稳定排序后的 `(path, size_bytes, sha256)` 序列计算：
    - `path<TAB>size<TAB>sha256<LF>`
    - 再整体做 `sha256`
  - 这样文件内容不变且路径/顺序稳定时，fingerprint 可复现。

## 5. 自检结果

### 5.1 必跑命令

```bash
git status --short
git diff --name-only origin/main...HEAD
pytest tests/datasets tests/artifacts
ruff check .
mypy .
```

### 5.2 输出摘要

- `git status --short`：
  - 开发完成前仅包含 `src/eval_platform/datasets/`、`tests/datasets/`、ADR、`current_status.md` 与 `report.md` 改动。
- `git diff --name-only origin/main...HEAD`：
  - 本轮提交前工作区只涉及：
    - `src/eval_platform/datasets/`
    - `tests/datasets/`
    - `docs/decisions/0011-raw-dataset-artifact.md`
    - `docs/ai/current_status.md`
    - `report.md`
  - 不包含 `chunking/`、`embeddings/`、`retrieval/`、`metrics/` 等越界目录。
- `pytest tests/datasets tests/artifacts`：
  - 通过，`86 passed`
- `ruff check .`：
  - 通过
- `mypy .`：
  - 通过，`Success: no issues found in 82 source files`

### 5.3 提交信息

- 是否已提交：`yes`
- commit subject：`Add raw dataset artifact`
- 验收者确认的最终 commit：

## 6. 风险与未决项

- 已知风险：
  - 当前 `ArtifactStore.put_file(...)` 仍以 `bytes` 为入参，所以虽然 hash 计算是流式的，写入前仍会在进程内暂存单文件字节内容。
- 未覆盖场景：
  - 本轮没有实现后续 `raw_dataset -> normalized_dataset` 依赖连接。
- 需要验收者重点检查的点：
  - `content_fingerprint_sha256` 的定义是否满足后续复现实验要求。
  - `raw_dataset` 是否继续放在 `datasets/` 下，还是未来应下沉到更通用的数据资产模块。

## 7. 交付结论

- 是否建议验收：`待测试完成后确认`
- 是否建议合并：`yes`
- 如果不能合并，卡点是什么：无
