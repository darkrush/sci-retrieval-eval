# 开发报告

本文件由开发 session 维护。验收 session 默认只检查这里，不追聊天记录。

## 1. 任务信息

- 任务名：`修正 query-only normalized 变化导致 corpus 全链路重建的问题`
- 当前分支：`feat/ifir-scifact-corpus-executor`
- 基线：`origin/main` / `4e03932 Add IFIRNFCorpus corpus asset executor (#56)`
- 完成时间：2026-06-09
- 实现提交 SHA：待提交后补充

## 2. 实现摘要

- 新增 normalized artifact metadata 字段：
  - `corpus_fingerprint_sha256`
  - 语义：只由 `corpus.jsonl` 稳定序列化字节计算，不包含 queries、qrels、IFIR instruction 或 effective query policy。
- `inventory_corpus_assets(...)` 会保留该字段；对历史 complete normalized artifact 若 manifest 缺字段，会只读 `corpus.jsonl` 兼容补算到 inventory summary，不写回 S3。
- corpus asset planner 支持 query-only normalized 变化：
  - raw fingerprint 匹配时 raw 可 reuse。
  - normalized full fingerprint 不匹配时 normalized 仍 create。
  - 如果旧 downstream source normalized 的 `corpus_fingerprint_sha256` 与 expected corpus fingerprint 一致，则旧 `chunked_corpus`、`embeddings`、ES、Milvus 可 reuse。
  - 如果 corpus fingerprint 缺失或不同，则不跨 normalized 复用 downstream。
- reused chunk / embedding / index step 的 source id 来自 reused manifest dependency，不再错误指向新 normalized artifact。
- 候选链选择优先级调整为：同 stage 下优先选择 normalized full fingerprint 精确匹配链；没有精确链时才选择 corpus-compatible 跨 normalized 链。

## 3. Executor 支持

保留并随本轮提交已有的 `IFIRScifact` executor 扩展：

- `scripts/execute_ifir_nfcorpus_corpus_assets.py` 支持 `IFIRNFCorpus` 和 `IFIRScifact`。
- 对应测试 `tests/scripts/test_execute_ifir_nfcorpus_corpus_assets.py` 已覆盖 IFIRScifact 接受路径。

## 4. Planner 行为

新增单测覆盖 query-only normalized 变化：

```text
raw_dataset: reuse
normalized_dataset: create
chunked_corpus: reuse
embeddings: reuse
elasticsearch_index: reuse
milvus_collection: reuse
```

同时覆盖 corpus fingerprint 不同或缺失时：

```text
raw_dataset: reuse
normalized_dataset: create
chunked_corpus: create
embeddings: create
elasticsearch_index: create
milvus_collection: create
```

既有 embedding fingerprint 变化测试保持通过：embedding 变化时 embeddings 和 Milvus 重建，ES 继续复用旧 chunks。

## 5. 真实 Dry-run

已运行只读 dry-run，未执行真实 embedding / ES / Milvus 写入：

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u NO_PROXY python3 scripts/build_real_corpus_assets.py \
  --config tmp/test_plan/phase3_config.yaml \
  --s3-prefix sciverse_benchmark/assets \
  --raw-prefix sciverse_benchmark/raw \
  --dataset all \
  --run-id testplan_phase4_five_smoke_20260609 \
  --reuse-existing \
  --output tmp/test_plan/phase4_five_corpus_plan_after_fix.json
```

action summary：

```text
IFIRNFCorpus: raw reuse, normalized reuse, chunks reuse, embeddings reuse, ES reuse, Milvus reuse
IFIRScifact: raw reuse, normalized create, chunks reuse, embeddings reuse, ES reuse, Milvus reuse
LitSearchRetrieval: raw reuse, normalized reuse, chunks reuse, embeddings reuse, ES reuse, Milvus reuse
NFCorpus: raw reuse, normalized reuse, chunks reuse, embeddings reuse, ES reuse, Milvus reuse
SciFact: raw reuse, normalized reuse, chunks reuse, embeddings reuse, ES reuse, Milvus reuse
```

IFIRScifact 不再要求重建 148 万 embeddings。

## 6. 测试与验证

已运行：

```bash
env PYTHONPATH=src pytest tests/corpus_assets tests/datasets/test_raw_normalize.py tests/scripts/test_execute_ifir_nfcorpus_corpus_assets.py
env PYTHONPATH=src pytest tests/experiments/test_runner.py
ruff check .
env PYTHONPATH=src pytest
mypy .
mypy src tests scripts
```

结果：

- corpus assets / raw normalize / executor tests：passed，62 passed
- experiment runner tests：passed，9 passed
- `ruff check .`：passed
- full pytest：passed，788 passed
- `mypy src tests scripts`：passed，197 source files
- `mypy .`：failed，仅因未跟踪临时文件 `tmp/test_plan/run_phase3_ifir_smoke.py`：
  - `config.elasticsearch` 类型为 `ElasticsearchConfig | None`
  - `config.milvus` 类型为 `MilvusConfig | None`
  - 该文件不在 git tracked files 中，本轮未修改

## 7. 外部服务访问

- 真实 S3：yes，只读 inventory / dry-run plan；未写入
- 真实 ES：no
- 真实 Milvus：no
- 真实 embedding：no
- 真实 rerank：no
- 真实 rewrite：no

## 8. 测试痕迹处理

- 未清理 S3 上已有的 incomplete IFIRScifact embeddings artifact。
- 本轮只读 dry-run 未新增真实 artifact。
- 是否清理历史测试痕迹仍留给验收 / 调度 session 决定。
