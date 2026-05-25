# 进度报告

## 当前阶段

artifact store、S3 backend、dataset schema、MTEB adapter、chunking schema、chunking runner 已合并到 `main`。当前分支实现一个小型基础设施 PR：version-pinned external chunker adapter。

## 已完成事项（main）

- Local + S3 artifact store
- normalized dataset schema + JSONL artifact 读写
- MTEB dataset adapter
- chunked corpus schema + ChunkerProvenance + artifact IO
- `inspect_git_repo` / `ensure_git_repo_clean`
- `ChunkingRunConfig` / `run_chunking` + injectable `ExternalChunker`
- dirty repo 安全边界、round-trip 与 config validation 测试
- ADR：`docs/decisions/0005-chunking-runner.md`
- `tests/chunking/test_git.py` / `tests/chunking/test_runner.py`

## 本次 PR

- 实现 external chunker repo 的版本约束校验
  - remote URL
  - commit SHA
  - clean state
- 实现薄的 Python callable external chunker adapter
- 实现 version-pinned external chunking helper
- 复用现有 `run_chunking(...)` 写出 `chunked_corpus` artifact
- 不实现 embedding / ES / Milvus / retrieval / metrics

## 已验证事项

- `pytest tests/chunking/test_external_repo.py tests/chunking/test_external_adapter.py tests/chunking/test_external_chunking_runner.py` 通过
- `ruff check src/eval_platform/chunking tests/chunking` 通过
- `mypy src/eval_platform/chunking tests/chunking` 通过
- 版本校验失败路径已覆盖：
  - remote URL mismatch
  - commit SHA mismatch
  - dirty repo
- adapter 返回 `ChunkRecord` / `dict` 两种路径均已覆盖
- version-pinned helper 会记录：
  - source dependency
  - external repo provenance
  - adapter metadata in `chunk_params`

## 当前限制

- 仅支持 Python callable adapter
- 不自动 `git fetch` 或 `git checkout`
- 用户必须事先准备好正确的外部 repo checkout
- 尚未接入真实 `sciverse_clean` chunk 模块路径

## 建议后续方向

- 定义 embedding schema 与 artifact 格式
- 下一步：`feat/embedding-schema`
