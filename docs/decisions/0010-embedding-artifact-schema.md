# ADR 0010: Embedding Artifact Schema

## Status

Accepted

## Context

当前主线已经能稳定产出：

- `normalized_dataset` artifact
- `chunked_corpus` artifact

下一阶段需要为 embedding runner 和向量索引构建准备稳定的中间产物格式，但当前还不适合直接接入真实 embedding API、批处理、重试、Milvus 或 ES。

因此需要先固定：

- embedding 内存 schema
- embedding JSONL 格式
- embeddings artifact read/write 逻辑
- 向量维度与 provenance 的一致性校验

## Decision

新增独立的 `embeddings` 模块，包含：

- `EmbeddingProvenance`
- `EmbeddingRecord`
- `EmbeddedCorpus`
- `dump_embeddings_jsonl(...)`
- `load_embeddings_jsonl(...)`
- `write_embeddings_artifact(...)`
- `read_embeddings_artifact(...)`

artifact 约定如下：

- `artifact_type = "embeddings"`
- 主数据文件为 `embeddings.jsonl`
- `_MANIFEST.json` 记录：
  - `embedding_count`
  - `unique_chunk_count`
  - `unique_doc_count`
  - `embedding_dim`
  - `provenance`
- `_SUCCESS` 继续作为完成标记，且必须最后写入

`EmbeddingRecord` 约束如下：

- `chunk_id` 非空
- `doc_id` 非空
- `vector` 非空
- `vector` 中所有值必须是 finite number

`write_embeddings_artifact(...)` 在写入前强制校验：

- 所有向量维度一致
- 向量维度与 `EmbeddingProvenance.embedding_dim` 一致

如果传入 `source_artifact_id`，则 manifest dependency 默认指向：

- `artifact_type = "chunked_corpus"`

## Consequences

优点：

- 后续 embedding runner 可以只负责“如何生成向量”，不用重新定义产物格式
- 后续 Milvus / ES index builder 可以只消费统一 embeddings artifact
- 维度错误会在 artifact 写入阶段尽早失败，而不是延迟到索引或检索阶段

限制：

- 本阶段不实现真实 embedding API
- 本阶段不实现 batching / retry / rate limit
- JSONL 不是最终唯一存储格式；如果后续需要大规模优化，可再引入 Parquet / NumPy shard 等格式

## Next Step

下一步实现 `feat/embedding-runner`，负责：

- 读取 `chunked_corpus`
- 调用注入式 fake/real embedder
- 产出 `embeddings` artifact
