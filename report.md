# 进度报告

## 当前阶段

`feat/artifact-store` 已完成本地实现，正在进行合并前小修（接口与 schema 稳定性）。

## 已完成事项

- 新建独立仓库：`sci-retrieval-eval`
- 初始化 git，并整理出 bootstrap 基线
- 写好项目协作规则：`AGENTS.md`
- 写好项目背景文档：`docs/ai/project_brief.md`
- 建立代码骨架：`src/eval_platform/`
  - `artifacts`
  - `datasets`
  - `chunking`
  - `embeddings`
  - `indexes`
  - `retrieval`
  - `mteb_adapter`
  - `metrics`
  - `frontend`
  - `cli`
- 建立测试目录（按模块组织）：
  - `tests/artifacts/`
  - `tests/integration/`（预留）
- 补齐 CLI 入口：`evalctl version`
- 补齐基础文档：
  - `README.md`
  - `docs/architecture.md`
  - `docs/decisions/0001-artifact-driven-eval.md`
  - `docs/ai/current_status.md`
  - `docs/ai/handoff_template.md`
  - `docs/ai/open_questions.md`
- 补齐 CI：`.github/workflows/ci.yml`
- 实现本地 artifact store：
  - `ArtifactManifest`
  - `ArtifactFile`
  - `ArtifactDependency`
  - `ArtifactStore`
  - `LocalArtifactStore`
- 补齐 artifact store 的关键约束：
  - 路径安全校验
  - manifest/path 一致性校验
  - `is_complete()` 同时要求 `_MANIFEST.json` 和 `_SUCCESS`
- 补齐 artifact store 单元测试（`tests/artifacts/`）：
  - manifest 读写
  - put/get/exists
  - `_SUCCESS` 完整性判断
  - path traversal 拒绝
  - manifest mismatch 拒绝

## 合并前小修（进行中）

- `ArtifactStore` 使用 `artifact_uri()`，抽象接口不再暴露 `Path`
- `ArtifactManifest` 增加 `schema_version`
- `ArtifactFile.checksum` 改为 `sha256`
- 补充 manifest schema 测试
- 统一文档中的测试目录描述

## 已验证事项

- `pip install -e ".[dev]"` 可通过
- `evalctl version` 可执行
- `pytest` 通过
- `ruff check .` 通过
- 包布局符合要求：只有 `src/eval_platform/`，没有根目录 `eval_platform/`
- 当前未引入 S3 / ES / Milvus / MTEB 业务逻辑
- 未发现硬编码的 endpoint、bucket、API key、token、password

## 当前仓库状态

- 主分支：`main`
- 当前开发分支：`feat/artifact-store`（已推送远端，ahead 2 / behind 0）
- artifact store 当前提交：`3f74870 Add local artifact store with manifest schema and path safety.`
- 合并前小修尚未提交

## 当前结论

- bootstrap 阶段已经完成
- 第一个核心模块 `artifact store` 方向正确，可作为第一版基础
- 建议完成合并前小修后再合并到 `main`
- 合并后下一步：`feat/s3-artifact-store`

## 建议下一阶段目标

- 在当前 artifact store 基础上补齐 S3 backend
- 增加 checksum / file metadata helper
- 继续保持 local/S3 backend 的统一 `ArtifactStore` 接口
- 继续保持“不引入 Redis / SQL / Airflow”的约束
