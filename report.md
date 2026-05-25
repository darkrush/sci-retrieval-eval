# 进度报告

## 当前阶段

`main` 已具备：

- artifact store
- S3 backend
- normalized dataset schema
- MTEB per-dataset normalizer registry
- chunked corpus schema
- chunking runner
- version-pinned Sciverse chunker adapter

当前分支 `feat/embedding-schema` 在此基础上固定 embedding 产物的 schema、JSONL 和 artifact read/write，作为后续 embedding runner 和向量索引前的稳定中间层。

## 本次开发

- 新增 `src/eval_platform/embeddings/schema.py`
  - `EmbeddingProvenance`
  - `EmbeddingRecord`
  - `EmbeddedCorpus`
- 新增 `src/eval_platform/embeddings/jsonl.py`
  - `dump_embeddings_jsonl(...)`
  - `load_embeddings_jsonl(...)`
- 新增 `src/eval_platform/embeddings/artifact.py`
  - `write_embeddings_artifact(...)`
  - `read_embeddings_artifact(...)`
  - `EmbeddingArtifactError`
- 更新 `src/eval_platform/embeddings/__init__.py`
  - 导出公共 schema / JSONL / artifact API

## Artifact 语义

当前 embeddings artifact 约定：

- `artifact_type = "embeddings"`
- 主数据文件：
  - `embeddings.jsonl`
- manifest metadata 系统字段：
  - `embedding_count`
  - `unique_chunk_count`
  - `unique_doc_count`
  - `embedding_dim`
  - `provenance`

写入时会强制校验：

- 所有 vector 维度一致
- 所有 vector 维度与 `EmbeddingProvenance.embedding_dim` 一致
- `vector` 中值必须是 finite number

如果提供 `source_artifact_id`，manifest dependency 默认指向：

- `artifact_type = "chunked_corpus"`

## 单元测试

已新增：

- `tests/embeddings/test_schema.py`
  - 非空字段校验
  - 维度和 finite number 校验
  - 默认 metadata 不共享引用
- `tests/embeddings/test_jsonl.py`
  - JSONL round-trip
  - 空输入
  - 空行忽略
  - 非法 JSON / schema 错误
- `tests/embeddings/test_artifact.py`
  - artifact 写入 / 读回
  - `_SUCCESS` 完整性检查
  - system metadata 不可被用户覆盖
  - source dependency 记录
  - 向量维度不一致时报错

## 结论

- 本 PR 只实现 embedding schema 和 artifact read/write
- 本 PR 不调用真实 embedding API
- 本 PR 不实现 batching / retry
- 本 PR 不实现 ES / Milvus / retrieval / metrics

## 建议后续方向

- 合并 `feat/embedding-schema`
- 然后开始 `feat/embedding-runner`
