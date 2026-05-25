# 进度报告

## 当前阶段

artifact store、S3 backend、dataset schema、MTEB adapter、chunking schema、chunking runner 已合并到 `main`。

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

## 本次修复

- 修复 `mteb_adapter` 对新版 MTEB task 布局的兼容问题
- 支持从 `task.dataset[subset][split]` 读取 `corpus/queries/relevant_docs`
- 支持将 `datasets.Dataset` 形式的 `corpus/queries` 转成内部所需 mapping
- 新增两条 smoke CLI：
  - `python -m eval_platform.cli.mteb_ifir_nfcorpus_smoke`
  - `python -m eval_platform.cli.ifir_nfcorpus_smoke`
- 补充 `tests/mteb_adapter/test_load.py` 对新版数据布局的覆盖

## 已验证事项

- `pytest tests/mteb_adapter/test_load.py` 通过
- `ruff check src/eval_platform/mteb_adapter/load.py tests/mteb_adapter/test_load.py` 通过
- `mypy src/eval_platform/mteb_adapter/load.py tests/mteb_adapter/test_load.py` 通过
- 真实 `mteb.load_data()` 的 `IFIRNFCorpus` smoke 已跑通
- 使用临时 git repo 与 fake chunker 成功产出：
  - `normalized_dataset`
  - `chunked_corpus`

## Smoke 结果

- run id: `smoke_retry_ifirnf2`
- normalized artifact:
  - `test_mteb_ifirnfcorpus_test_smoke_retry_ifirnf2`
  - `corpus=3633`
  - `queries=86`
  - `qrels=242`
- chunked artifact:
  - `test_mteb_ifirnfcorpus_test_smoke_retry_ifirnf2_fake_chunks`
  - `chunks=3633`
- chunked manifest 记录了：
  - source dependency -> normalized artifact
  - fake chunker git commit sha
  - `is_dirty=false`
  - `chunk_params`

## 建议后续方向

- 定义 embedding schema 与 artifact 格式
- 后续可按需接入真实 external chunker adapter
