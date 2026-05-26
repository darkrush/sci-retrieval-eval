# 0011. Raw Dataset Artifact

- Status: Accepted
- Date: 2026-05-26

## Context

当前主线已经具备 `normalized_dataset`、`chunked_corpus` 和 `embeddings` artifact，但原始输入文件在进入标准化前仍缺少一个显式、可审计的落盘层。

对于较大或外部依赖较多的数据集，直接从内存对象开始标准化有几个问题：

1. 原始数据版本、文件列表和文件内容缺少稳定快照。
2. 下载/cache/load 失败时，很难判断问题发生在“拉取原始数据”还是“标准化逻辑”。
3. 后续多人复现实验时，无法直接核对最初消费的原始文件集合是否一致。

## Decision

新增 `raw_dataset` artifact，作为数据链路的第一层显式快照。

其约束如下：

1. artifact 类型固定为 `raw_dataset`。
2. 原始文件内容按稳定相对路径写入 artifact 内的 `files/` 目录。
3. manifest metadata 至少记录：
   - `stage`
   - `source_type`
   - `source_uri`
   - `dataset_name`
   - `dataset_revision`
   - `file_count`
   - `total_size_bytes`
   - `files`
   - `content_fingerprint_sha256`
   - `import_parameters`
4. 单文件 `sha256` 与 dataset 级 `content_fingerprint_sha256` 都按稳定排序生成。
5. hash 计算必须流式读取文件内容，不要求为了满足当前 `ArtifactStore` 接口而改造整个存储抽象。
6. 第一阶段支持两种导入方式：
   - 从本地目录导入
   - 从既有 S3 prefix 导入

## Consequences

1. 后续 `normalized_dataset` 应依赖 `raw_dataset` 作为上游输入身份。
2. raw 层与 normalized 层职责分离后，下载/拉取问题与标准化问题可以分开定位。
3. 当前 `ArtifactStore.put_file(...)` 仍以 `bytes` 为输入，因此导入时虽然 hash 是流式计算，写入前仍会在进程内暂存单文件字节内容。
4. 若后续 raw 文件规模继续增大，可以再单独演进 `ArtifactStore` 的 streaming upload 能力，而不影响本次 schema 与 manifest 约定。
