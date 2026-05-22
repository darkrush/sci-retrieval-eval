# 进度报告

## 当前阶段

`main` 已合并本地 artifact store。当前在 `feat/s3-artifact-store` 分支实现 S3 backend。

## 已完成事项

- bootstrap 基线与项目协作规则
- 本地 artifact store（已合并到 `main`）
  - `ArtifactManifest` / `ArtifactStore` / `LocalArtifactStore`
  - 路径安全、manifest 一致性、`_SUCCESS` 完整性校验
  - `tests/artifacts/` 单元测试

## 进行中

- `S3ArtifactStore` 实现（`src/eval_platform/artifacts/s3.py`）
- fake S3 client 单元测试（`tests/artifacts/test_s3_store.py`）
- `boto3` 作为 optional dependency（`[s3]` extra）

## 已验证事项

- 测试使用 fake client，不访问真实 S3
- 无硬编码 endpoint / bucket / API key / token
- 复用已有 path validation 逻辑

## 当前仓库状态

- 主分支：`main`（含 artifact store merge）
- 当前开发分支：`feat/s3-artifact-store`

## 当前结论

- Local + S3 双 backend 是 pipeline 统一读写 artifact 的前提
- 本 PR 不包含 dataset / MTEB / ES / Milvus / embedding 业务逻辑

## 建议下一阶段目标

- 合并 S3 artifact store PR
- 开 `feat/dataset-schema`：定义 `CorpusRecord` / `QueryRecord` / `QrelRecord`
- 继续保持小 PR、不引入 Redis / SQL / Airflow
