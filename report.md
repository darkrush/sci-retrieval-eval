# 进度报告

## 当前阶段

`main` 已具备 artifact store、S3 backend、dataset schema、MTEB adapter、chunking schema 和 chunking runner。当前分支上的 version-pinned external chunker adapter / Sciverse admin-ingest adapter 已完成本地实现，待 PR / merge review。

## 已完成事项（main）

- Local + S3 artifact store
- normalized dataset schema + JSONL artifact 读写
- MTEB dataset adapter
- chunked corpus schema + `ChunkerProvenance` + artifact IO
- `inspect_git_repo` / `ensure_git_repo_clean`
- `ChunkingRunConfig` / `run_chunking` + injectable `ExternalChunker`
- MTEB 新 layout 兼容修复
- 真实 `IFIRNFCorpus` MTEB -> normalized_dataset -> fake chunk 本地/S3 smoke 验证

## 本次开发

- 保留并复用现有 version-pinned external repo 校验：
  - remote URL
  - commit SHA
  - clean state
- 新增 `SciverseAdminIngestChunkerConfig`
- 新增 `SciverseAdminIngestExternalChunker`
- 新增 `run_version_pinned_sciverse_chunking(...)`
- 通过动态导入 `<repo>/python_services/admin-ingest`，把外部 repo 的 `chunk_ndjson_records(...)` 接入当前 `run_chunking(...)`
- 保持 provenance / dependency / manifest 统一收口
- 不实现 embedding / ES / Milvus / retrieval / metrics

## 已验证事项

- `pytest tests/chunking/test_external_repo.py tests/chunking/test_external_adapter.py tests/chunking/test_external_chunking_runner.py tests/chunking/test_sciverse_adapter.py` 通过
- `ruff check src/eval_platform/chunking tests/chunking` 通过
- `mypy src/eval_platform/chunking tests/chunking` 通过
- 新增 fake `sciverse` repo 测试覆盖：
  - 动态导入 `python_services/admin-ingest`
  - `NormalizedDataset -> NDJSON -> chunk_ndjson_records -> ChunkRecord`
  - version-pinned helper 写出 `chunked_corpus` artifact
  - dependency、repo provenance、chunk params 正确落入 manifest
- 通用 `PythonCallableExternalChunker` 已补 `sys.modules` 隔离：
  - 不同 repo 的同名 module 不再串用
  - 缺失 module 错误路径已覆盖

## 当前限制

- 仍未直接提供用户界面的 `SCIVERSE_PATH` 命令入口；当前是库级 adapter
- 真实 `sciverse_clean` smoke 还需要再跑一轮，确认外部 repo 当前字段与 fake repo 假设一致
- 不自动 `git fetch` 或 `git checkout`
- 用户必须事先准备好正确的外部 repo checkout

## 建议后续方向

- 合并这条 `sciverse` adapter 分支
- 然后开始 `feat/embedding-schema`
