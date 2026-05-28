# 开发报告

本文件由开发 session 维护。验收 session 默认只检查这里，不追聊天记录。

## 1. 任务信息

- 任务名：`Track B / B1 Asset Fingerprint Spec`
- 当前分支：`feat/asset-fingerprint-spec`
- 对应指令文件：本地未发现 `TASK.md`，本轮以用户提供的 session init 指令为任务来源
- 开始时间：2026-05-28
- 完成时间：2026-05-28
- 实现提交 SHA：提交后由 `git log -1 --oneline` 确认；提交内容无法自引用自身 SHA

## 2. 实现内容

新增：

- `src/eval_platform/assets/__init__.py`
  - 导出 asset fingerprint public helpers。
- `src/eval_platform/assets/fingerprint.py`
  - `AssetFingerprintError`
  - `AssetFingerprint`
  - `canonical_json_hash(...)`
  - `build_asset_fingerprint(...)`
  - `assert_no_secret_keys(...)`
  - raw / normalized / chunked / embeddings / ES / Milvus / retrieval / metrics stage component builders。
- `tests/assets/__init__.py`
- `tests/assets/test_fingerprint.py`
  - 覆盖 canonical hash、secret guard、operational identity guard、schema validation、component builders 和等价性示例。
- `docs/operations/experiment_variants.md`
  - 记录后续实验变体、资产复用和最小重算规划语义。

更新：

- `docs/architecture.md`
  - 新增 `Asset identity and equivalence` 章节。
  - 明确 artifact id / `run_id` 不是资产身份，dependency 只证明 lineage，资产等价由 `asset_fingerprint` 判断。

## 3. Fingerprint 语义

`canonical_json_hash(...)`：

- 使用 `json.dumps(..., sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)`。
- 返回 sha256 hex digest。
- dict key 顺序不同但内容相同会得到相同 hash。
- 非 JSON-serializable value、非 string dict key、NaN/Infinity 会抛 `AssetFingerprintError`。
- 不会 silently stringify 任意对象。

`AssetFingerprint`：

- `fingerprint_version >= 1`。
- `artifact_type` 非空。
- `sha256` 非空。
- `components` 使用 `Field(default_factory=dict)`，避免共享默认引用。

`build_asset_fingerprint(...)`：

- hash payload 包含 `fingerprint_version`、`artifact_type`、`components`。
- 会复制和规范化 components，不修改传入对象。

secret / identity guard：

- 递归拒绝包含 `api_key`、`access_key`、`secret`、`password`、`token`、`authorization` 的 key，大小写不敏感。
- 递归拒绝 `run_id`、`artifact_id`、`created_at`、`created_by` 这类操作性身份 key。
- 只检查 key，不检查 value。
- 不禁止 `endpoint_alias`，也不禁止 `endpoint_url`；文档建议优先使用 alias。

## 4. 与 run_id 的关系

当前系统仍可能在 artifact id、Elasticsearch index name、Milvus collection name 中携带
`run_id`。这些是物理产物或外部资源的操作性定位信息，不是逻辑资产身份。

本轮新增的 fingerprint helper 不接收 `run_id` 参数，并且在通用 payload 里拒绝 `run_id`
key。后续 B2 / B3 可在不改变既有命名的前提下，用 fingerprint 判断不同 run 产出的资产
是否逻辑等价。

## 5. 验证结果

已运行：

```bash
PYTHONPATH=src pytest tests/assets/test_fingerprint.py
PYTHONPATH=src pytest
ruff check .
mypy .
```

结果：

- `PYTHONPATH=src pytest tests/assets/test_fingerprint.py`
  - `24 passed in 0.09s`
- `PYTHONPATH=src pytest`
  - `624 passed in 2.96s`
- `ruff check .`
  - `All checks passed!`
- `mypy .`
  - `Success: no issues found in 175 source files`

环境说明：

- 本 shell 中普通 `python -c "import eval_platform"` 会解析到兄弟目录
  `/home/qiujiuantao/codex_project/sci-base/sci-retrieval-eval/src/eval_platform/__init__.py`。
- 因此本轮 pytest 使用 `PYTHONPATH=src`，确保测试当前
  `/home/qiujiuantao/codex_project/sci-base/sci-retrieval-eval-dev` 工作区源码。

## 6. 外部服务访问

- 是否访问真实 S3：`no`
- 是否访问真实 ES：`no`
- 是否访问真实 Milvus：`no`
- 是否访问真实 embedding：`no`
- 是否访问真实 rerank：`no`
- 是否访问真实 rewrite：`no`

本轮只运行本地单元测试。

## 7. 未实现项

按 B1 范围，本轮未实现：

- planner 行为变更。
- artifact writer 全量接入 `asset_fingerprint`。
- corpus asset stage override。
- minimal rebuild planner。
- benchmark variant spec。
- force rebuild stages。
- pinned artifacts。
- 真实 baseline 或真实外部服务运行。

## 8. 风险与建议

- 当前只是 fingerprint 基础设施；现有 planner 仍按 complete marker 和 dependency chain 做复用判断。
- 后续 B2 建议先把 asset fingerprint 写入 manifest metadata，再在 reuse planning 中增加
  `complete + artifact_type + dependency-compatible chain + fingerprint match` 四项联合校验。
- 对于用户指出的 `run_id` 问题，建议保留现有 artifact/resource 命名作为物理定位方式，
  但所有逻辑等价判断都迁移到 `asset_fingerprint`。
