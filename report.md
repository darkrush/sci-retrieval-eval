# 开发报告

本文件由开发 session 维护。验收 session 默认只检查这里，不追聊天记录。

## 1. 任务信息

- 任务名：`自动生成 corpus expected fingerprints，避免误复用旧 IFIR 资产`
- 当前分支：`fix/corpus-asset-expected-fingerprints`
- 基线：`origin/main` / `ec70cac Fail recall@inf on incomplete retrieval artifacts (#54)`
- 完成时间：2026-06-09
- 实现提交 SHA：提交后由 `git log -1 --oneline` 确认

## 2. 背景

执行 `test_plan.md` 时发现：

- 当前代码已支持 IFIR `mteb_text_plus_instruction` query policy。
- 但 S3 上旧 IFIR normalized artifacts 仍是旧口径，只保存原始 query，metadata 只有 `instruction`。
- 常规 `scripts/build_real_corpus_assets.py --reuse-existing` 会继续复用旧 IFIR normalized/chunks/embedding/ES/Milvus 全链条。

这会导致后续 smoke 或 baseline 产出“看起来完整但 query 口径错误”的结果。

## 3. 实现摘要

新增：

- `src/eval_platform/corpus_assets/expected_fingerprints.py`

核心行为：

- 根据当前 dataset registry、raw artifact fingerprint 和 raw normalizer spec 自动生成 corpus expected fingerprints。
- IFIRNFCorpus / IFIRScifact 的 normalized expected fingerprint 会包含：

```text
query_text_policy=mteb_text_plus_instruction
```

- 非 IFIR 数据集不会被错误加入 IFIR query policy。
- 用户显式传入 `expected_asset_fingerprints_by_slug` 时，显式值优先。

接入点：

- `scripts/build_real_corpus_assets.py`
  - `--reuse-existing` 时自动计算 expected fingerprints 并传给 planner。
- `src/eval_platform/experiments/corpus_assets.py`
  - experiment corpus asset resolution 使用同一套 expected fingerprint 逻辑。

## 4. 真实 dry-run 复验

命令：

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u NO_PROXY python3 scripts/build_real_corpus_assets.py \
  --config /home/qiujiuantao/codex_project/sci-base/sciverse_benchmark/config.yaml \
  --s3-prefix sciverse_benchmark/assets \
  --raw-prefix sciverse_benchmark/raw \
  --dataset IFIRNFCorpus \
  --run-id testplan_ifir_policy_20260609 \
  --reuse-existing \
  --output tmp/test_plan/phase2_after_fix_ifir_plan.json
```

结果：

| stage | action |
| --- | --- |
| raw_dataset | reuse |
| normalized_dataset | create |
| chunked_corpus | create |
| embeddings | create |
| elasticsearch_index | create |
| milvus_collection | create |

dry-run 输出包含：

```text
expected_asset_fingerprints.normalized_dataset=8c0d4a2487cca7b4b2f8939276e423b8e58dacb9defd4ad8407da6bdb24483fc
expected_asset_fingerprints.raw_dataset=8d8b22573747ce0c5625fd62684a3e4b8d3c03b081cb4721db1dc2c674f795e7
```

结论：Phase 2 的 planner reuse 阻塞已修复。默认 `--reuse-existing` 不再复用旧 IFIR normalized 及其下游链。

## 5. 测试更新

新增/更新：

- `tests/corpus_assets/test_expected_fingerprints.py`
  - 覆盖 IFIR normalized expected fingerprint 包含 `query_text_policy=mteb_text_plus_instruction`。
  - 覆盖非 IFIR 不加入 IFIR query policy。
  - 覆盖显式 expected fingerprints 优先。
- `tests/experiments/test_corpus_assets.py`
  - 覆盖 experiment corpus asset resolution 会把 expected fingerprints 传给 planner。
- `tests/scripts/test_build_real_corpus_assets.py`
  - 覆盖脚本 `--reuse-existing` 会把 expected fingerprints 传给 planner。
- `tests/experiments/test_runner.py`
  - 旧 fixture 复用场景改为显式传入 fixture 自身 fingerprints，避免和新的默认防误复用策略冲突。

## 6. 验证结果

已运行：

```bash
env PYTHONPATH=src pytest tests/corpus_assets tests/experiments tests/scripts
env PYTHONPATH=src pytest tests/analysis/test_recall_inf.py tests/datasets/test_raw_normalize.py tests/mteb_adapter
ruff check .
env PYTHONPATH=src pytest
mypy .
```

结果：

- `tests/corpus_assets tests/experiments tests/scripts`: passed, 38 passed
- `tests/analysis/test_recall_inf.py tests/datasets/test_raw_normalize.py tests/mteb_adapter`: passed, 112 passed
- `ruff check .`: passed
- full `pytest`: passed, 774 passed
- `mypy .`: passed

## 7. 外部服务访问

- 真实 S3：yes，只读 inventory / manifest / dry-run 检查
- 真实 ES：no
- 真实 Milvus：no
- 真实 embedding：no
- 真实 rerank：no
- 真实 rewrite：no

## 8. 剩余事项

`test_plan.md` 的 Phase 3 尚未执行。原因：

- Phase 3 需要可用的新 IFIR normalized/chunk/embedding/ES/Milvus 资产。
- 当前仓库只有 `build_real_corpus_assets.py` dry-run planner，`--execute` 明确未实现。
- 修复后 planner 正确要求创建新 IFIR normalized 及下游资产，但当前没有正式脚本执行这条真实构建链。

下一步应补真实 corpus asset build runner/脚本，或使用已有外部 runner 先构建新 IFIR assets，再继续 Phase 3 smoke。
