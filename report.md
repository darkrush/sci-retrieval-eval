# 开发报告

本文件由开发 session 维护。验收 session 默认只检查这里，不追聊天记录。

## 1. 任务信息

- 任务名：`补 IFIRNFCorpus 真实 corpus asset 构建入口，解锁 Phase 3 smoke`
- 当前分支：`feat/ifir-corpus-asset-execute`
- 基线：`origin/main` / `7f48fa3 Fix corpus asset expected fingerprint reuse (#55)`
- 是否 cherry-pick `6985bf1`：否，#55 已合入 main
- 完成时间：2026-06-09
- 实现提交 SHA：提交后由 `git log -1 --oneline` 确认

## 2. 实现摘要

新增专用入口：

```text
scripts/execute_ifir_nfcorpus_corpus_assets.py
```

能力范围：

- 仅支持 `IFIRNFCorpus`。
- 基于 `build_expected_asset_fingerprints_by_slug(...)` 和 `build_plan_for_datasets(...)` 生成执行计划。
- 根据 planner action 决定每个 stage 是 `reuse` 还是 `create`。
- 支持从已有 raw artifact 或 immutable raw S3 prefix 出发。
- 支持创建：
  - `normalized_dataset`
  - `chunked_corpus`
  - `embeddings`
  - `elasticsearch_index`
  - `milvus_collection`
- 拒绝写入 `test_` prefix。
- 当前只允许写入 `sciverse_benchmark/assets`。
- `--yes` 前只输出 plan，不写入。

## 3. 安全与验证逻辑

新增 preflight：

- 如果需要创建 `chunked_corpus`，必须存在：
  - `config.chunking.repo_path`
  - `config.chunking.repo_remote`
  - `config.chunking.commit_sha`
- 如果需要创建 `embeddings`，必须存在 embedding model / dim / endpoint URL。
- 如果需要创建 ES index，必须存在 `elasticsearch.url`。
- 如果需要创建 Milvus collection，必须存在 `milvus.address`。

新增 normalized 验证：

- manifest metadata 必须有 `query_text_policy=mteb_text_plus_instruction`。
- `queries.jsonl` 抽样必须包含：
  - `source_query_text`
  - `instruction`
  - `effective_query_text`
  - `query_text_policy`
  - `instruction_startswith_query_text`
- `QueryRecord.text` 必须等于 `effective_query_text`。

新增入库 manifest 验证：

- `chunk_count == embedding_count`
- ES manifest 必须有 `index_name`
- ES `verified_document_count == chunk_count`
- Milvus manifest 必须有 `collection_name`
- Milvus `verified_entity_count == embedding_count`

## 4. 真实执行检查

no-write plan 命令：

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u NO_PROXY python3 scripts/execute_ifir_nfcorpus_corpus_assets.py \
  --config /home/qiujiuantao/codex_project/sci-base/sciverse_benchmark/config.yaml \
  --s3-prefix sciverse_benchmark/assets \
  --raw-prefix sciverse_benchmark/raw \
  --run-id testplan_ifir_policy_20260609 \
  --reuse-existing \
  --output tmp/test_plan/phase3_execute_ifir_plan.json
```

结果：

- 成功输出 planner plan。
- 未写入。
- 计划显示：
  - raw_dataset: reuse
  - normalized_dataset: create
  - chunked_corpus: create
  - embeddings: create
  - elasticsearch_index: create
  - milvus_collection: create

真实执行命令：

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u NO_PROXY python3 scripts/execute_ifir_nfcorpus_corpus_assets.py \
  --config /home/qiujiuantao/codex_project/sci-base/sciverse_benchmark/config.yaml \
  --s3-prefix sciverse_benchmark/assets \
  --raw-prefix sciverse_benchmark/raw \
  --run-id testplan_ifir_policy_20260609 \
  --reuse-existing \
  --yes \
  --output tmp/test_plan/phase3_execute_ifir_plan_with_yes.json
```

结果：

```text
ERROR: Cannot create chunked_corpus: config.chunking.repo_path, repo_remote and commit_sha are required
```

这是预期的安全失败：当前真实 config 缺少外部 chunker 仓库配置。preflight 在任何写入前失败。

S3 半成品检查：

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u NO_PROXY python3 scripts/view_s3_artifacts.py \
  --config /home/qiujiuantao/codex_project/sci-base/sciverse_benchmark/config.yaml \
  --s3-prefix sciverse_benchmark/assets \
  --artifact-id-contains testplan_ifir_policy_20260609 \
  --fingerprint any \
  --limit 50 \
  --output tmp/test_plan/phase3_after_preflight_inventory.json
```

结果：

```text
artifacts: []
```

确认没有写出半成品 artifact。

## 5. 测试更新

新增：

```text
tests/scripts/test_execute_ifir_nfcorpus_corpus_assets.py
```

覆盖：

- 拒绝非 `IFIRNFCorpus` dataset。
- 拒绝 `test_` prefix。
- 脚本先调用 planner，未传 `--yes` 时只输出 plan 并拒绝写入。
- normalized 验证能识别旧 IFIR artifact 缺 `query_text_policy`。
- normalized 验证接受 effective query artifact。
- preflight 能在缺 chunking config 时拒绝执行。
- 入库 count 校验失败时报错。

## 6. 验证结果

已运行：

```bash
env PYTHONPATH=src pytest tests/corpus_assets tests/scripts tests/datasets/test_raw_normalize.py
ruff check .
mypy .
env PYTHONPATH=src pytest
```

结果：

- `tests/corpus_assets tests/scripts tests/datasets/test_raw_normalize.py`: passed, 61 passed
- `ruff check .`: passed
- `mypy .`: passed
- full `pytest`: passed, 781 passed

## 7. 外部服务访问

- 真实 S3：yes，只读 plan / inventory；未写入
- 真实 ES：no
- 真实 Milvus：no
- 真实 embedding：no
- 真实 rerank：no
- 真实 rewrite：no

## 8. 剩余阻塞

`test_plan.md` Phase 3 仍未完成。

阻塞原因不是代码入口缺失，而是当前真实配置缺少外部 chunker 配置：

```text
chunking.repo_path
chunking.repo_remote
chunking.commit_sha
```

补齐上述 config 后，可以重跑真实构建命令。构建出新的 IFIRNFCorpus corpus assets 后，再继续 Phase 3 的 E1-E4 smoke。
