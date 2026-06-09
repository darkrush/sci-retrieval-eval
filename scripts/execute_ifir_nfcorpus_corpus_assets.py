#!/usr/bin/env python3
"""Execute a narrow IFIR corpus asset chain from real S3 raw data.

This script is intentionally narrow: it only supports IFIR datasets so smoke
tests can build corrected effective-query assets without turning the
five-dataset planner into a broad execution framework.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from eval_platform.artifacts.metadata_keys import (  # noqa: E402
    METADATA_KEY_COLLECTION_NAME,
    METADATA_KEY_INDEX_NAME,
)
from eval_platform.artifacts.types import (  # noqa: E402
    CHUNKED_CORPUS_ARTIFACT_TYPE,
    ELASTICSEARCH_INDEX_ARTIFACT_TYPE,
    EMBEDDINGS_ARTIFACT_TYPE,
    MILVUS_COLLECTION_ARTIFACT_TYPE,
    NORMALIZED_DATASET_ARTIFACT_TYPE,
    RAW_DATASET_ARTIFACT_TYPE,
)
from eval_platform.chunking import ChunkingRunConfig, run_chunking  # noqa: E402
from eval_platform.chunking.external_repo import (  # noqa: E402
    ExternalChunkerRepoSpec,
    verify_external_chunker_repo,
)
from eval_platform.chunking.progress import ProgressEvent, ProgressReporter  # noqa: E402
from eval_platform.chunking.sciverse_adapter import (  # noqa: E402
    SciverseAdminIngestChunkerConfig,
    SciverseAdminIngestExternalChunker,
)
from eval_platform.config import PlatformConfig  # noqa: E402
from eval_platform.corpus_assets import (  # noqa: E402
    CorpusAssetError,
    build_expected_asset_fingerprints_by_slug,
    build_plan_for_datasets,
    dataset_specs_for_selection,
    inventory_corpus_assets,
    load_config_and_client,
    make_s3_artifact_store,
    output_payload,
    raw_prefix_exists,
    raw_prefix_key,
)
from eval_platform.datasets import (  # noqa: E402
    RawToNormalizedConfig,
    S3RawFileOpener,
    import_raw_dataset_from_s3_prefix,
    normalize_raw_dataset_artifact,
)
from eval_platform.embeddings import (  # noqa: E402
    EmbeddingRunConfig,
    HTTPEmbeddingClient,
    HTTPEmbeddingClientConfig,
    MultiEndpointEmbeddingConfig,
    run_embedding,
    run_embedding_consistency_check,
)
from eval_platform.indexes import (  # noqa: E402
    ElasticsearchIngestConfig,
    HTTPElasticsearchClient,
    HTTPElasticsearchClientConfig,
    MilvusIngestConfig,
    PymilvusMilvusClient,
    PymilvusMilvusClientConfig,
    run_elasticsearch_ingest,
    run_milvus_ingest,
)

DEFAULT_IFIR_TASK_NAME = "IFIRNFCorpus"
SUPPORTED_IFIR_TASK_NAMES = frozenset({"IFIRNFCorpus", "IFIRScifact"})
IFIR_QUERY_TEXT_POLICY = "mteb_text_plus_instruction"


class IFIRCorpusAssetExecuteError(Exception):
    """Raised when the narrow IFIR corpus asset executor cannot proceed."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--s3-prefix", required=True)
    parser.add_argument("--raw-prefix", default="sciverse_benchmark/raw")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--dataset", default=DEFAULT_IFIR_TASK_NAME)
    parser.add_argument("--reuse-existing", action="store_true")
    parser.add_argument("--yes", action="store_true", help="Confirm real writes")
    parser.add_argument("--output", type=Path, default=None)
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    _validate_args(args)
    config, client = load_config_and_client(args.config)
    if not config.s3.bucket:
        raise IFIRCorpusAssetExecuteError("config.s3.bucket is required")

    spec = dataset_specs_for_selection(args.dataset)[0]
    task_name = spec.task_name
    store = make_s3_artifact_store(
        config=config,
        s3_prefix=args.s3_prefix,
        client=client,
    )
    inventory = inventory_corpus_assets(
        store=store,
        raw_client=client,
        bucket=config.s3.bucket,
        raw_prefix=args.raw_prefix,
        datasets=[spec],
    )
    expected_asset_fingerprints_by_slug = build_expected_asset_fingerprints_by_slug(
        config=config,
        datasets=[spec],
        inventory=inventory,
    )
    raw_exists = raw_prefix_exists(
        client,
        bucket=config.s3.bucket,
        prefix=raw_prefix_key(args.raw_prefix, spec),
    )
    plan = build_plan_for_datasets(
        datasets=[spec],
        run_id=args.run_id,
        bucket=config.s3.bucket,
        raw_prefix=args.raw_prefix,
        s3_prefix=args.s3_prefix,
        raw_exists_by_slug={spec.slug: raw_exists},
        reuse_existing=args.reuse_existing,
        inventory=inventory,
        expected_asset_fingerprints_by_slug=expected_asset_fingerprints_by_slug,
    )
    output_payload(
        {
            "kind": "ifir_corpus_asset_execute_plan",
            "execute": bool(args.yes),
            "plan": plan,
        },
        args.output,
    )

    if not args.yes:
        raise IFIRCorpusAssetExecuteError("Refusing real writes without --yes")

    _preflight_create_stages(config, plan)
    progress = _print_progress
    code_git_sha = _current_git_sha()
    stage_results = _execute_plan(
        config=config,
        raw_client=client,
        store=store,
        plan=plan,
        task_name=task_name,
        dataset_slug=spec.slug,
        raw_prefix=args.raw_prefix,
        run_id=args.run_id,
        code_git_sha=code_git_sha,
        progress_reporter=progress,
    )
    summary = {
        "kind": "ifir_corpus_asset_execute_result",
        "dataset": task_name,
        "run_id": args.run_id,
        "s3_prefix": args.s3_prefix,
        "stage_results": stage_results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def _validate_args(args: argparse.Namespace) -> None:
    if args.dataset not in SUPPORTED_IFIR_TASK_NAMES:
        raise IFIRCorpusAssetExecuteError(
            "Only IFIRNFCorpus and IFIRScifact are supported, "
            f"got {args.dataset!r}"
        )
    if not str(args.s3_prefix).strip():
        raise IFIRCorpusAssetExecuteError("--s3-prefix must not be empty")
    normalized_prefix = str(args.s3_prefix).strip("/")
    if normalized_prefix.startswith("test_") or "/test_" in normalized_prefix:
        raise IFIRCorpusAssetExecuteError("Refusing to write to test_ S3 prefix")
    if normalized_prefix != "sciverse_benchmark/assets":
        raise IFIRCorpusAssetExecuteError(
            "This executor only writes to sciverse_benchmark/assets"
        )
    if not str(args.run_id).strip():
        raise IFIRCorpusAssetExecuteError("--run-id must not be empty")


def _execute_plan(
    *,
    config: PlatformConfig,
    raw_client: Any,
    store: Any,
    plan: dict[str, Any],
    task_name: str,
    dataset_slug: str,
    raw_prefix: str,
    run_id: str,
    code_git_sha: str,
    progress_reporter: ProgressReporter,
) -> list[dict[str, Any]]:
    dataset_plan = plan["datasets"][task_name]
    steps = dataset_plan["steps"]
    step_by_type = {step["artifact_type"]: step for step in steps}
    stage_results: list[dict[str, Any]] = []

    raw_step = step_by_type[RAW_DATASET_ARTIFACT_TYPE]
    if raw_step["action"] == "create":
        spec = dataset_specs_for_selection(task_name)[0]
        raw_manifest = import_raw_dataset_from_s3_prefix(
            store,
            raw_step["artifact_id"],
            client=raw_client,
            bucket=config.s3.bucket or "",
            prefix=raw_prefix_key(raw_prefix, spec),
            dataset_name=task_name,
            source_uri=raw_step["raw_source_uri"],
            import_parameters={"raw_format": "jsonl_tsv", "split": "test"},
            created_by="validator",
            code_git_sha=code_git_sha,
            metadata={"dataset_slug": dataset_slug, "task_name": task_name},
        )
        stage_results.append(_manifest_result("raw_import", raw_manifest))
    else:
        _require_complete(store, RAW_DATASET_ARTIFACT_TYPE, raw_step["artifact_id"])
        stage_results.append(_reuse_result("raw_import", raw_step))

    normalized_step = step_by_type[NORMALIZED_DATASET_ARTIFACT_TYPE]
    if normalized_step["action"] == "create":
        normalized_manifest = normalize_raw_dataset_artifact(
            store,
            store,
            RawToNormalizedConfig(
                source_artifact_id=normalized_step["source_artifact_id"],
                output_artifact_id=normalized_step["artifact_id"],
                dataset_name=task_name,
                split="test",
                created_by="validator",
                code_git_sha=code_git_sha,
                metadata={"dataset_slug": dataset_slug},
            ),
            opener=S3RawFileOpener(raw_client),
            progress_reporter=progress_reporter,
        )
        stage_results.append(_manifest_result("raw_to_normalized", normalized_manifest))
    else:
        _require_complete(store, NORMALIZED_DATASET_ARTIFACT_TYPE, normalized_step["artifact_id"])
        stage_results.append(_reuse_result("raw_to_normalized", normalized_step))
    validate_ifir_normalized_artifact(store, normalized_step["artifact_id"])

    chunks_step = step_by_type[CHUNKED_CORPUS_ARTIFACT_TYPE]
    if chunks_step["action"] == "create":
        chunk_manifest = _run_sciverse_chunking(
            config=config,
            store=store,
            source_artifact_id=chunks_step["source_artifact_id"],
            output_artifact_id=chunks_step["artifact_id"],
            code_git_sha=code_git_sha,
            task_name=task_name,
            dataset_slug=dataset_slug,
            progress_reporter=progress_reporter,
        )
        stage_results.append(_manifest_result("chunking", chunk_manifest))
    else:
        _require_complete(store, CHUNKED_CORPUS_ARTIFACT_TYPE, chunks_step["artifact_id"])
        stage_results.append(_reuse_result("chunking", chunks_step))

    embedding_step = step_by_type[EMBEDDINGS_ARTIFACT_TYPE]
    if embedding_step["action"] == "create":
        embedding_manifest = _run_embedding(
            config=config,
            store=store,
            source_artifact_id=embedding_step["source_artifact_id"],
            output_artifact_id=embedding_step["artifact_id"],
            code_git_sha=code_git_sha,
            task_name=task_name,
            dataset_slug=dataset_slug,
            progress_reporter=progress_reporter,
        )
        stage_results.append(_manifest_result("embedding", embedding_manifest))
    else:
        _require_complete(store, EMBEDDINGS_ARTIFACT_TYPE, embedding_step["artifact_id"])
        stage_results.append(_reuse_result("embedding", embedding_step))

    es_step = step_by_type[ELASTICSEARCH_INDEX_ARTIFACT_TYPE]
    if es_step["action"] == "create":
        es_manifest = run_elasticsearch_ingest(
            store,
            store,
            ElasticsearchIngestConfig(
                source_artifact_id=es_step["source_artifact_id"],
                output_artifact_id=es_step["artifact_id"],
                index_name=es_step[METADATA_KEY_INDEX_NAME],
                overwrite_existing=True,
                created_by="validator",
                code_git_sha=code_git_sha,
                metadata={"dataset_slug": dataset_slug, "task_name": task_name},
            ),
            _make_es_client(config),
            progress_reporter=progress_reporter,
        )
        stage_results.append(_manifest_result("elasticsearch_ingest", es_manifest))
    else:
        _require_complete(store, ELASTICSEARCH_INDEX_ARTIFACT_TYPE, es_step["artifact_id"])
        stage_results.append(_reuse_result("elasticsearch_ingest", es_step))

    milvus_step = step_by_type[MILVUS_COLLECTION_ARTIFACT_TYPE]
    if milvus_step["action"] == "create":
        milvus_manifest = run_milvus_ingest(
            store,
            store,
            store,
            MilvusIngestConfig(
                chunked_corpus_artifact_id=milvus_step["chunked_corpus_artifact_id"],
                embeddings_artifact_id=milvus_step["embeddings_artifact_id"],
                output_artifact_id=milvus_step["artifact_id"],
                collection_name=milvus_step[METADATA_KEY_COLLECTION_NAME],
                overwrite_existing=True,
                vector_dim=config.embedding.dim,
                index_params={
                    "index_type": (
                        config.milvus.index_type if config.milvus else None
                    )
                    or "HNSW"
                },
                created_by="validator",
                code_git_sha=code_git_sha,
                metadata={"dataset_slug": dataset_slug, "task_name": task_name},
            ),
            _make_milvus_client(config),
            progress_reporter=progress_reporter,
        )
        stage_results.append(_manifest_result("milvus_ingest", milvus_manifest))
    else:
        _require_complete(store, MILVUS_COLLECTION_ARTIFACT_TYPE, milvus_step["artifact_id"])
        stage_results.append(_reuse_result("milvus_ingest", milvus_step))

    validate_ingest_manifests(store, dataset_plan["resolved_artifact_ids"])
    return stage_results


def _preflight_create_stages(config: PlatformConfig, plan: dict[str, Any]) -> None:
    if len(plan["datasets"]) != 1:
        raise IFIRCorpusAssetExecuteError("executor plan must contain exactly one dataset")
    dataset_plan = next(iter(plan["datasets"].values()))
    create_stages = {
        step["artifact_type"]
        for step in dataset_plan["steps"]
        if step.get("action") == "create"
    }
    if CHUNKED_CORPUS_ARTIFACT_TYPE in create_stages:
        chunking = config.chunking
        if not (chunking.repo_path and chunking.repo_remote and chunking.commit_sha):
            raise IFIRCorpusAssetExecuteError(
                "Cannot create chunked_corpus: config.chunking.repo_path, "
                "repo_remote and commit_sha are required"
            )
    if EMBEDDINGS_ARTIFACT_TYPE in create_stages:
        if not config.embedding.model:
            raise IFIRCorpusAssetExecuteError(
                "Cannot create embeddings: embedding.model is required"
            )
        if not config.embedding.dim:
            raise IFIRCorpusAssetExecuteError("Cannot create embeddings: embedding.dim is required")
        if not any(endpoint.url for endpoint in config.embedding.endpoints):
            raise IFIRCorpusAssetExecuteError(
                "Cannot create embeddings: embedding.endpoints must include at least one URL"
            )
    if ELASTICSEARCH_INDEX_ARTIFACT_TYPE in create_stages:
        if config.elasticsearch is None or not config.elasticsearch.url:
            raise IFIRCorpusAssetExecuteError(
                "Cannot create elasticsearch_index: elasticsearch.url is required"
            )
    if MILVUS_COLLECTION_ARTIFACT_TYPE in create_stages:
        if config.milvus is None or not config.milvus.address:
            raise IFIRCorpusAssetExecuteError(
                "Cannot create milvus_collection: milvus.address is required"
            )


def _run_sciverse_chunking(
    *,
    config: PlatformConfig,
    store: Any,
    source_artifact_id: str,
    output_artifact_id: str,
    code_git_sha: str,
    task_name: str,
    dataset_slug: str,
    progress_reporter: ProgressReporter,
) -> Any:
    chunking = config.chunking
    if not (chunking.repo_path and chunking.repo_remote and chunking.commit_sha):
        raise IFIRCorpusAssetExecuteError(
            "config.chunking.repo_path, repo_remote and commit_sha are required"
        )
    verify_external_chunker_repo(
        ExternalChunkerRepoSpec(
            repo_path=chunking.repo_path,
            expected_remote_url=chunking.repo_remote,
            expected_commit_sha=chunking.commit_sha,
        )
    )
    chunk_params = dict(chunking.chunk_params)
    file_record_num = _optional_int(chunk_params.pop("file_record_num", None))
    chunker_kwargs = _sciverse_chunker_kwargs(chunk_params)
    chunker_config = SciverseAdminIngestChunkerConfig(
        repo_path=chunking.repo_path,
        **chunker_kwargs,
    )
    final_chunk_params = {**chunk_params, **chunker_config.chunk_params()}
    final_chunk_params.update(
        {
            "adapter_type": "sciverse_admin_ingest",
            "adapter_package_subdir": "python_services/admin-ingest",
        }
    )
    return run_chunking(
        store,
        ChunkingRunConfig(
            source_artifact_id=source_artifact_id,
            output_artifact_id=output_artifact_id,
            chunker_name=chunking.chunker_name or "sciverse_admin_ingest",
            chunker_repo_path=chunking.repo_path,
            file_record_num=file_record_num,
            chunk_params=final_chunk_params,
            created_by="validator",
            code_git_sha=code_git_sha,
            metadata={"dataset_slug": dataset_slug, "task_name": task_name},
        ),
        SciverseAdminIngestExternalChunker(chunker_config),
        progress_reporter=progress_reporter,
    )


def _run_embedding(
    *,
    config: PlatformConfig,
    store: Any,
    source_artifact_id: str,
    output_artifact_id: str,
    code_git_sha: str,
    task_name: str,
    dataset_slug: str,
    progress_reporter: ProgressReporter,
) -> Any:
    endpoints = _selected_embedding_endpoint_configs(config)
    clients = [HTTPEmbeddingClient(endpoint) for endpoint in endpoints]
    consistency_config = MultiEndpointEmbeddingConfig(
        endpoints=endpoints,
    )
    consistency = run_embedding_consistency_check(
        consistency_config,
        clients,
        input_text="sci-retrieval-eval embedding consistency probe",
    )
    if not consistency.passed:
        raise IFIRCorpusAssetExecuteError(
            f"Embedding consistency check failed: {consistency.failure_reason}"
        )
    return run_embedding(
        store,
        store,
        EmbeddingRunConfig(
            source_artifact_id=source_artifact_id,
            output_artifact_id=output_artifact_id,
            model_name=config.embedding.model or "BAAI/bge-m3",
            embedding_dim=config.embedding.dim or 1024,
            provider="http",
            endpoint_id=endpoints[0].endpoint_id,
            endpoint_ids=[endpoint.endpoint_id or endpoint.endpoint_url for endpoint in endpoints],
            batch_size=config.embedding.batch_size,
            timeout_seconds=config.embedding.timeout_sec,
            consistency_check=consistency,
            created_by="validator",
            code_git_sha=code_git_sha,
            metadata={"dataset_slug": dataset_slug, "task_name": task_name},
        ),
        clients[0],
        progress_reporter=progress_reporter,
    )


def _selected_embedding_endpoint_configs(config: PlatformConfig) -> list[HTTPEmbeddingClientConfig]:
    candidates: list[tuple[str, str]] = []
    for index, endpoint in enumerate(config.embedding.endpoints):
        if not endpoint.url:
            continue
        endpoint_id = f"endpoint[{index}]"
        candidates.append((endpoint_id, endpoint.url))
    if not candidates:
        raise IFIRCorpusAssetExecuteError("config.embedding.endpoints must not be empty")
    preferred = [
        item for item in candidates if ":3886/" in item[1] or ":3887/" in item[1]
    ]
    selected = preferred or candidates
    headers = []
    endpoint_by_url = {endpoint.url: endpoint for endpoint in config.embedding.endpoints}
    for endpoint_id, url in selected:
        endpoint = endpoint_by_url[url]
        header: dict[str, str] = {}
        if endpoint.api_key:
            header["Authorization"] = f"Bearer {endpoint.api_key}"
        headers.append(
            HTTPEmbeddingClientConfig(
                endpoint_url=url,
                endpoint_id=endpoint_id,
                model_name=config.embedding.model,
                timeout_seconds=config.embedding.timeout_sec or 120.0,
                headers=header,
                batch_size=config.embedding.batch_size or 64,
                max_retries=config.embedding.max_retries or 0,
            )
        )
    return headers


def validate_ifir_normalized_artifact(store: Any, artifact_id: str) -> None:
    manifest = store.read_manifest(NORMALIZED_DATASET_ARTIFACT_TYPE, artifact_id)
    if manifest.metadata.get("query_text_policy") != IFIR_QUERY_TEXT_POLICY:
        raise IFIRCorpusAssetExecuteError(
            f"normalized artifact {artifact_id!r} missing {IFIR_QUERY_TEXT_POLICY}"
        )
    payload = store.get_file(NORMALIZED_DATASET_ARTIFACT_TYPE, artifact_id, "queries.jsonl")
    for line in payload.decode("utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        metadata = row.get("metadata")
        if not isinstance(metadata, dict):
            raise IFIRCorpusAssetExecuteError("query metadata must be a mapping")
        required = {
            "source_query_text",
            "instruction",
            "effective_query_text",
            "query_text_policy",
            "instruction_startswith_query_text",
        }
        missing = sorted(required - set(metadata))
        if missing:
            raise IFIRCorpusAssetExecuteError(f"query metadata missing keys: {missing}")
        if metadata.get("query_text_policy") != IFIR_QUERY_TEXT_POLICY:
            raise IFIRCorpusAssetExecuteError("query metadata has wrong query_text_policy")
        if row.get("text") != metadata.get("effective_query_text"):
            raise IFIRCorpusAssetExecuteError("QueryRecord.text must equal effective_query_text")
        return
    raise IFIRCorpusAssetExecuteError("queries.jsonl contains no query rows")


def validate_ingest_manifests(store: Any, artifact_ids: dict[str, str]) -> None:
    chunk_manifest = store.read_manifest(
        CHUNKED_CORPUS_ARTIFACT_TYPE,
        artifact_ids[CHUNKED_CORPUS_ARTIFACT_TYPE],
    )
    embedding_manifest = store.read_manifest(
        EMBEDDINGS_ARTIFACT_TYPE,
        artifact_ids[EMBEDDINGS_ARTIFACT_TYPE],
    )
    es_manifest = store.read_manifest(
        ELASTICSEARCH_INDEX_ARTIFACT_TYPE,
        artifact_ids[ELASTICSEARCH_INDEX_ARTIFACT_TYPE],
    )
    milvus_manifest = store.read_manifest(
        MILVUS_COLLECTION_ARTIFACT_TYPE,
        artifact_ids[MILVUS_COLLECTION_ARTIFACT_TYPE],
    )
    chunk_count = _required_int(chunk_manifest.metadata, "chunk_count")
    embedding_count = _required_int(embedding_manifest.metadata, "embedding_count")
    if chunk_count != embedding_count:
        raise IFIRCorpusAssetExecuteError(
            f"chunk_count and embedding_count mismatch: {chunk_count} != {embedding_count}"
        )
    if es_manifest.metadata.get(METADATA_KEY_INDEX_NAME) is None:
        raise IFIRCorpusAssetExecuteError("ES manifest missing index_name")
    if _required_int(es_manifest.metadata, "verified_document_count") != chunk_count:
        raise IFIRCorpusAssetExecuteError("ES verified_document_count does not match chunk_count")
    if milvus_manifest.metadata.get(METADATA_KEY_COLLECTION_NAME) is None:
        raise IFIRCorpusAssetExecuteError("Milvus manifest missing collection_name")
    if _required_int(milvus_manifest.metadata, "verified_entity_count") != embedding_count:
        raise IFIRCorpusAssetExecuteError(
            "Milvus verified_entity_count does not match embedding_count"
        )


def _require_complete(store: Any, artifact_type: str, artifact_id: str) -> None:
    if not store.is_complete(artifact_type, artifact_id):
        raise IFIRCorpusAssetExecuteError(f"Artifact is incomplete: {artifact_type}/{artifact_id}")


def _make_es_client(config: PlatformConfig) -> HTTPElasticsearchClient:
    if config.elasticsearch is None or not config.elasticsearch.url:
        raise IFIRCorpusAssetExecuteError("config.elasticsearch.url is required")
    return HTTPElasticsearchClient(
        HTTPElasticsearchClientConfig(
            base_url=config.elasticsearch.url,
            username=config.elasticsearch.username,
            password=config.elasticsearch.password,
        )
    )


def _make_milvus_client(config: PlatformConfig) -> PymilvusMilvusClient:
    if config.milvus is None or not config.milvus.address:
        raise IFIRCorpusAssetExecuteError("config.milvus.address is required")
    return PymilvusMilvusClient(
        PymilvusMilvusClientConfig(
            uri=config.milvus.address,
            username=config.milvus.username,
            password=config.milvus.password,
            db_name=config.milvus.db_name,
        )
    )


def _sciverse_chunker_kwargs(chunk_params: dict[str, Any]) -> dict[str, Any]:
    allowed = set(SciverseAdminIngestChunkerConfig.model_fields) - {"repo_path"}
    return {key: value for key, value in chunk_params.items() if key in allowed}


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _required_int(metadata: dict[str, Any], key: str) -> int:
    value = metadata.get(key)
    if not isinstance(value, int):
        raise IFIRCorpusAssetExecuteError(f"manifest metadata {key!r} must be an int")
    return value


def _current_git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
    except Exception:
        return "unknown"
    return result.stdout.strip() or "unknown"


def _manifest_result(stage: str, manifest: Any) -> dict[str, Any]:
    return {
        "stage": stage,
        "action": "create",
        "artifact_type": manifest.artifact_type,
        "artifact_id": manifest.artifact_id,
    }


def _reuse_result(stage: str, step: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": stage,
        "action": "reuse",
        "artifact_type": step["artifact_type"],
        "artifact_id": step["artifact_id"],
    }


def _print_progress(event: ProgressEvent) -> None:
    total = "?" if event.total is None else str(event.total)
    message = event.message or ""
    print(f"[progress] {event.stage} {event.current}/{total} {message}")


def main() -> int:
    try:
        run(build_parser().parse_args())
    except (CorpusAssetError, IFIRCorpusAssetExecuteError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
