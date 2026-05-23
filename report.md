# 进度报告

## 当前阶段

Local + S3 artifact store 已合并到 `main`。当前在 `feat/dataset-schema` 分支实现 normalized dataset schema。

## 已完成事项（main）

- bootstrap 基线与项目协作规则
- Local artifact store + S3 artifact store
- `ArtifactManifest` / `ArtifactStore` 基础层

## 进行中（feat/dataset-schema）

- normalized dataset schema（`CorpusRecord` / `QueryRecord` / `QrelRecord` / `NormalizedDataset`）
- JSONL 读写（`dump_jsonl` / `load_jsonl`）
- normalized dataset artifact 读写（`write_normalized_dataset_artifact` / `read_normalized_dataset_artifact`）
- `ArtifactIncompleteError`
- ADR：`docs/decisions/0002-normalized-dataset-schema.md`
- `tests/datasets/` 单元测试

## 本 PR 范围

- 只实现 normalized dataset schema 和 JSONL artifact 读写
- 不包含 MTEB 下载 / adapter / ES / Milvus / embedding / retrieval

## 已验证事项

- 测试不访问真实 S3 或网络
- 无硬编码 endpoint / bucket / API key / token
- `pytest` / `ruff check .` 通过

## 当前结论

- dataset schema 是 MTEB adapter 的前置条件
- 合并后下一步：`feat/mteb-dataset-adapter`

## 建议下一阶段目标

- 实现 MTEB dataset adapter，把 MTEB 原始结构转换为 normalized dataset artifact
- 继续保持小 PR、不引入 Redis / SQL / Airflow
