# 开发计划

## 1. 规划目标

本计划服务于当前阶段目标：

1. 统一离线评测流程。
2. 建立可审计、可复现的 corpus artifact 链路。
3. 在 artifact 身份稳定后，再闭合 embedding、索引、检索和指标。

核心原则：第一层落盘数据必须是原始数据快照，不再把 `mteb.load_data()` 的内存结果视为系统输入边界。

原因：

1. 大数据集一次性 `load` 可能失败或耗尽内存。
2. 不同机器的 HuggingFace / MTEB cache、版本、revision 可能不一致。
3. 只有 normalized dataset 没有 raw snapshot，无法审计标准化前到底读了哪些字节。

## 2. Artifact 主链路

完整 corpus 链路调整为：

```text
raw_dataset -> normalized_dataset -> chunked_corpus -> embeddings -> es_ingest_manifest
                                                        -> milvus_ingest_manifest
```

其中：

1. `raw_dataset` 是第一层可信输入，记录原始文件、来源、版本、hash、下载/导入方式。
2. `normalized_dataset` 是 `raw_dataset` 的标准化产物，只能依赖明确的 raw artifact。
3. `chunked_corpus` 是 `normalized_dataset` 的切片产物，必须记录 sciverse_clean 版本与入参。
4. `embeddings` 是 `chunked_corpus` 的向量产物，必须记录 API、入参、一致性预检查。
5. ES / Milvus ingest manifest 是 embeddings 和索引参数的入库记录。

## 3. 阶段划分

### 阶段 A：Raw Dataset Artifact

目标：把原始数据先落 S3，形成可审计的 raw artifact。

本阶段应完成：

1. `raw_dataset` schema / manifest。
2. 支持从已有 S3 raw prefix 导入 raw artifact。
3. 支持大文件流式读取和 hash 统计，不要求一次性加载全量数据。
4. manifest 记录来源信息：source type、repo/dataset 名称、revision、文件列表、文件大小、sha256、created_at、tool version。
5. raw artifact 写入 `_MANIFEST.json` 和 `_SUCCESS`。

本阶段不做：

1. 不直接 chunk。
2. 不直接 embedding。
3. 不直接访问 ES / Milvus。
4. 不要求一次性解决所有外部数据源下载；先支持“已上传到 S3 raw 区”的导入。

参考实现：

1. `sciverse_benchmark/format_scripts/common.py` 中的 `read_s3_jsonl`、`read_s3_parquet`、hash 统计方式。
2. `sciverse_benchmark/docs/corpus_format_pipeline.md` 中的 raw 输入路径和 manifest 字段。

### 阶段 B：Raw To Normalized

目标：把 normalized dataset 明确改为 raw artifact 的产物。

本阶段应完成：

1. normalizer 从 `raw_dataset` artifact 读取输入，而不是直接调用 `mteb.load_data()` 后处理内存对象。
2. 支持 JSONL / Parquet 的流式标准化。
3. 输出 `corpus.jsonl`、`queries.jsonl`、`qrels.jsonl` 和 normalized manifest。
4. manifest 记录 raw dependency、normalizer 名称、入参、输入/输出 hash、成功/失败状态。
5. 对 IFIRNFCorpus / NFCorpus 这类可能共享 corpus 的数据，保留 content fingerprint，用于判断是否可复用后续 chunk / embedding。

本阶段可保留 MTEB adapter，但定位要改变：

1. MTEB 可以作为 raw import/download helper。
2. MTEB 不能再作为 normalized artifact 的不可见输入来源。

### 阶段 C：Chunked Corpus

目标：让标准化数据通过 sciverse_clean 的 chunk 逻辑生成 chunk artifact。

本阶段应完成：

1. 继续使用 sciverse_clean / admin-ingest chunk 逻辑。
2. 记录外部仓库 remote、commit、branch、dirty 状态。
3. 记录 chunk 参数和输入 normalized artifact。
4. 输出 `chunks.jsonl`、manifest、`_SUCCESS`。

### 阶段 D：Embedding Artifact

目标：把 `chunked_corpus -> embeddings` 做扎实。

本阶段应完成：

1. embedding API 配置和 provenance。
2. 多 endpoint 同文本一致性预检查。
3. base64 float32 向量落盘。
4. S3 输出和可读回。

### 阶段 E：索引级 Artifact 身份

目标：让 embeddings 之后的索引阶段也具备可审计身份。

本阶段应完成：

1. Milvus ingest manifest。
2. ES ingest manifest。
3. index 参数、collection/index 名称、输入 embeddings artifact、成功/失败状态。

### 阶段 F：检索运行与指标

目标：统一“评测时到底调用了谁、用了哪些参数”，并让最终分数可追溯。

本阶段应完成：

1. retrieval run config schema。
2. retrieval trace / predictions artifact。
3. metrics artifact。
4. report artifact。

## 4. 当前推荐顺序

建议按下面顺序推进：

1. `raw_dataset` artifact。
2. `raw_dataset -> normalized_dataset`。
3. `normalized_dataset -> chunked_corpus`。
4. `chunked_corpus -> embeddings`。
5. ES / Milvus ingest manifest。
6. retrieval / metrics。

优先级调整原因：

1. embedding 已具备基础能力，但其输入如果不可审计，后续结果仍不可复现。
2. 大数据集不能依赖一次性 `load` 成内存对象。
3. raw artifact 是后面所有差异排查的根。

## 5. 当前建议的下一个开发任务

下一个开发任务建议是：

`feat/raw-dataset-artifact`

任务目标：

1. 新增 `raw_dataset` artifact 类型。
2. 支持从 S3 raw prefix 导入 raw artifact。
3. 记录文件列表、大小、sha256、source metadata、manifest、`_SUCCESS`。
4. 增加小文件测试和 fake S3 / local store 测试。

完成后再做：

`feat/raw-to-normalized-dataset`

该任务负责把 IFIRNFCorpus 等数据的标准化改成读取 raw artifact，而不是直接依赖 `mteb.load_data()`。

## 6. 完成标准

当以下条件满足时，才算 corpus 输入层真正完成：

1. 别人可以只根据 raw manifest 找到并校验原始输入文件。
2. normalized manifest 明确依赖某个 raw artifact。
3. 标准化过程可以流式处理大数据集，不要求一次性 load 全量。
4. raw / normalized / chunk / embedding 每层都有独立 manifest 和 `_SUCCESS`。
5. 不需要阅读聊天记录也能复现实验输入。
