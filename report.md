# 开发报告

本文件由开发 session 维护。验收 session 默认只检查这里，不追聊天记录。

## 1. 任务信息

- 任务名：`IFIR effective query policy 验收返工`
- 当前分支：`feat/ifir-effective-query-policy`
- 基线：`origin/main` / `5692468 feat: add recall at inf metric (#50)`
- 完成时间：2026-06-09
- 实现提交 SHA：`128b6ba Fix IFIR effective query policy`
- 前次报告提交 SHA：`5002d86 Update IFIR policy report`
- 本轮返工提交 SHA：提交后由 `git log -1 --oneline` 确认；提交内容无法自引用自身 SHA

## 2. 实现摘要

本轮把 IFIR effective query 构造固化到 raw-to-normalized 阶段：

- `IFIRNFCorpus` 和 `IFIRScifact` 默认使用 `mteb_text_plus_instruction`。
- IFIR normalized `QueryRecord.text` 现在是实际送入后续 embedding / retrieval 的 effective query。
- query metadata 保留：
  - `source_query_text`
  - `instruction`
  - `effective_query_text`
  - `query_text_policy`
  - `instruction_startswith_query_text`
- manifest metadata 对 IFIR 记录：
  - `has_instructions`
  - `query_text_policy`
  - `effective_query_text_field`
  - `source_query_text_metadata_key`
  - `instruction_startswith_query_text_count`
- 普通 `NFCorpus` / `SciFact` 不设置 IFIR policy，不改写 query text。
- MTEB adapter 的 IFIR normalizer 现在同样执行 MTEB effective query policy：
  - `IFIRNFCorpusNormalizer`
  - `IFIRScifactNormalizer`
- 如果 MTEB adapter query payload 已经有 `effective_query_text`，或显式标记
  `query_text_policy == "mteb_loader_effective_text"`，则信任已有 effective text，不再次拼接。

## 3. IFIR policy 行为

`mteb_text_plus_instruction`：

```text
effective_query_text = query_text + " " + instruction
```

即使 `instruction.startswith(query_text)` 为 `True`，也不去重。MTEB pinned IFIR 数据当前会出现 query 文本重复一次，这是 MTEB loader 行为和 pinned revision 共同定义出的可复现口径。

`ifir_original_query_plus_instruction_once`：

```text
effective_query_text = query_text + " " + instruction
```

但如果 instruction 已经以 query text 开头，会抛出 `RawNormalizeError`，避免原始 IFIR 官方数据或已合成 query 被二次拼接。

缺失 instruction 的 IFIR query 会抛出 `RawNormalizeError`，不会静默退化为普通 query。

## 4. 测试覆盖

新增/更新测试覆盖：

- `IFIRNFCorpus` MTEB raw 格式 `Q` + `Q I` 输出 `Q Q I`。
- `IFIRScifact` 同样使用 `mteb_text_plus_instruction`。
- query metadata 保留 source query、instruction、effective query、policy 和 startswith 标志。
- manifest metadata 记录 policy 和 `instruction_startswith_query_text_count`。
- 非 IFIR `NFCorpus` / `SciFact` 不写入 IFIR policy，query text 不被改写。
- `ifir_original_query_plus_instruction_once` 正常拼一次。
- `ifir_original_query_plus_instruction_once` 遇到 instruction 已含 query 时失败。
- 缺失 instruction 的 IFIR query 明确失败。
- MTEB adapter 不对已经由 loader 合成过的 query 二次拼接。
- `IFIRNFCorpusNormalizer().normalize(...)` 遇到 `{text: "Q", instruction: "Q I"}` 输出
  `QueryRecord.text == "Q Q I"`。
- `IFIRScifactNormalizer().normalize(...)` 同样覆盖。
- instruction 不以 query 开头时输出 `Q I`，并记录
  `instruction_startswith_query_text is False`。

## 5. 验证结果

已运行：

```bash
env PYTHONPATH=src pytest tests/mteb_adapter tests/datasets/test_raw_normalize.py
env PYTHONPATH=src pytest
ruff check .
mypy .
```

结果：

- `env PYTHONPATH=src pytest tests/mteb_adapter tests/datasets/test_raw_normalize.py`
  - `74 passed in 0.25s`
- `env PYTHONPATH=src pytest`
  - `767 passed in 2.66s`
- `ruff check .`
  - `All checks passed!`
- `mypy .`
  - `Success: no issues found in 190 source files`

## 6. 兼容性影响

本轮会改变新生成的 IFIR normalized dataset：`QueryRecord.text` 从原始 query 变为 effective query。
因此下游 retrieval / metrics artifact 以及依赖 normalized query text 的 artifact fingerprint 会变化。
这是预期变化，因为此前 IFIR 可能没有实际使用 instruction。

已有已生成 artifact 不会被本轮代码自动重建；需要后续调度显式重建 IFIR normalized/downstream 资产。

## 7. 外部服务访问

- 是否访问真实 S3：`no`
- 是否访问真实 ES：`no`
- 是否访问真实 Milvus：`no`
- 是否访问真实 embedding：`no`
- 是否访问真实 rerank：`no`
- 是否访问真实 rewrite：`no`

## 8. 未实现项

- 未重跑真实五数据集实验。
- 未重建 S3 corpus / embedding / ES / Milvus 资产。
- 未修改 retrieval / benchmark runner 主流程。
- 未实现新的实验脚本。
