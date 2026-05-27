"""Shared helpers for five-dataset corpus asset inventory and dry-run planning."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from eval_platform.artifacts import ArtifactManifest, ArtifactStore, S3ArtifactStore
from eval_platform.artifacts.store import SUCCESS_MARKER
from eval_platform.config import PlatformConfig, dump_redacted_config, load_platform_config

ARTIFACT_STAGE_ORDER = [
    "raw_dataset",
    "normalized_dataset",
    "chunked_corpus",
    "embeddings",
    "elasticsearch_index",
    "milvus_collection",
]

STAGE_SUFFIX = {
    "raw_dataset": "raw",
    "normalized_dataset": "normalized",
    "chunked_corpus": "chunks",
    "embeddings": "embeddings",
    "elasticsearch_index": "es_index",
    "milvus_collection": "milvus_collection",
}

_SENSITIVE_KEY_PARTS = (
    "access_key",
    "api_key",
    "authorization",
    "password",
    "secret",
    "token",
)

_MANIFEST_SUMMARY_KEYS = {
    "dataset",
    "dataset_name",
    "task_name",
    "split",
    "normalizer_name",
    "corpus_count",
    "query_count",
    "qrel_count",
    "chunk_count",
    "embedding_count",
    "unique_chunk_count",
    "unique_doc_count",
    "embedding_dim",
    "source_artifact_id",
    "raw_dataset_artifact_id",
    "source_normalized_dataset_artifact_id",
    "source_chunked_corpus_artifact_id",
    "chunked_corpus_artifact_id",
    "embeddings_artifact_id",
    "index_name",
    "collection_name",
    "indexed_count",
    "inserted_count",
    "failed_count",
    "verified_count",
    "verified_document_count",
    "verified_entity_count",
}


class CorpusAssetError(Exception):
    """Raised when corpus asset inventory or planning fails."""


@dataclass(frozen=True)
class DatasetSpec:
    """One target dataset and its immutable raw S3 layout."""

    task_name: str
    slug: str
    raw_dir: str
    raw_format: str
    expected_raw_files: tuple[str, ...]
    notes: str


TARGET_DATASETS: tuple[DatasetSpec, ...] = (
    DatasetSpec(
        task_name="IFIRNFCorpus",
        slug="ifir_nfcorpus",
        raw_dir="ifir_nfcorpus",
        raw_format="jsonl_tsv",
        expected_raw_files=(
            "corpus.jsonl",
            "queries.jsonl",
            "instructions.jsonl",
            "qrels/test.tsv",
        ),
        notes="IFIR layout with query instructions.",
    ),
    DatasetSpec(
        task_name="NFCorpus",
        slug="nfcorpus",
        raw_dir="nfcorpus",
        raw_format="jsonl_tsv",
        expected_raw_files=("corpus.jsonl", "queries.jsonl", "qrels/test.tsv"),
        notes="BEIR-style JSONL corpus/queries plus test qrels TSV.",
    ),
    DatasetSpec(
        task_name="IFIRScifact",
        slug="ifir_scifact",
        raw_dir="ifir_scifact",
        raw_format="jsonl_tsv",
        expected_raw_files=(
            "corpus.jsonl",
            "queries.jsonl",
            "instructions.jsonl",
            "qrels/test.tsv",
        ),
        notes="IFIR layout with query instructions.",
    ),
    DatasetSpec(
        task_name="SciFact",
        slug="scifact",
        raw_dir="scifact",
        raw_format="jsonl_tsv",
        expected_raw_files=("corpus.jsonl", "queries.jsonl", "qrels/test.tsv"),
        notes="BEIR-style JSONL corpus/queries plus test qrels TSV.",
    ),
    DatasetSpec(
        task_name="LitSearchRetrieval",
        slug="litsearch",
        raw_dir="litsearch",
        raw_format="parquet_dir_shards",
        expected_raw_files=(
            "corpus/test-00000-of-00001.parquet",
            "queries/test-00000-of-00001.parquet",
            "qrels/test-00000-of-00001.parquet",
        ),
        notes="MTEB parquet shard layout.",
    ),
)

DATASETS_BY_NAME = {spec.task_name: spec for spec in TARGET_DATASETS}
DATASETS_BY_SLUG = {spec.slug: spec for spec in TARGET_DATASETS}


def dataset_specs_for_selection(selection: str) -> list[DatasetSpec]:
    """Return target dataset specs for one CLI selection."""

    if selection == "all":
        return list(TARGET_DATASETS)
    if selection in DATASETS_BY_NAME:
        return [DATASETS_BY_NAME[selection]]
    if selection in DATASETS_BY_SLUG:
        return [DATASETS_BY_SLUG[selection]]
    valid = sorted([spec.task_name for spec in TARGET_DATASETS] + ["all"])
    raise CorpusAssetError(f"Unknown dataset {selection!r}; expected one of {valid}")


def artifact_ids_for_dataset(spec: DatasetSpec, run_id: str) -> dict[str, str]:
    """Generate stable artifact ids for one dataset/run."""

    if not run_id.strip():
        raise CorpusAssetError("run_id must not be empty")
    return {
        artifact_type: f"{spec.slug}_{run_id}_{suffix}"
        for artifact_type, suffix in STAGE_SUFFIX.items()
    }


def index_name_for_dataset(spec: DatasetSpec, run_id: str) -> str:
    """Generate the Elasticsearch index name for one dataset/run."""

    return f"{spec.slug}_{run_id}_es"


def collection_name_for_dataset(spec: DatasetSpec, run_id: str) -> str:
    """Generate the Milvus collection name for one dataset/run."""

    return f"{spec.slug}_{run_id}_milvus"


def s3_uri(bucket: str, *parts: str) -> str:
    """Build an s3:// URI from a bucket and key parts."""

    key = "/".join(part.strip("/") for part in parts if part.strip("/"))
    return f"s3://{bucket}/{key}" if key else f"s3://{bucket}"


def raw_prefix_key(raw_prefix: str, spec: DatasetSpec) -> str:
    """Return the immutable raw prefix key for a dataset."""

    return "/".join(part.strip("/") for part in (raw_prefix, spec.raw_dir) if part.strip("/"))


def raw_prefix_uri(bucket: str, raw_prefix: str, spec: DatasetSpec) -> str:
    """Return the immutable raw prefix URI for a dataset."""

    return s3_uri(bucket, raw_prefix_key(raw_prefix, spec))


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if any(part in key.lower() for part in _SENSITIVE_KEY_PARTS):
                out[key] = "***"
            else:
                out[key] = _redact(item)
        return out
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def safe_json_dumps(payload: Any) -> str:
    """Serialize a payload after redacting sensitive keys."""

    return json.dumps(_redact(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def make_s3_client(config: PlatformConfig) -> Any:
    """Create a boto3 S3 client from platform config."""

    try:
        import boto3
    except ImportError as exc:
        raise CorpusAssetError(
            "boto3 is required for real S3 inventory; install the s3 extra"
        ) from exc
    return boto3.client(
        "s3",
        endpoint_url=config.s3.endpoint,
        aws_access_key_id=config.s3.access_key_id,
        aws_secret_access_key=config.s3.secret_access_key,
    )


def make_s3_artifact_store(
    *,
    config: PlatformConfig,
    s3_prefix: str,
    client: Any,
) -> S3ArtifactStore:
    """Create the artifact store for a target S3 prefix."""

    if not config.s3.bucket:
        raise CorpusAssetError("config.s3.bucket is required")
    return S3ArtifactStore(
        bucket=config.s3.bucket,
        prefix=s3_prefix.strip("/"),
        client=client,
    )


def raw_prefix_exists(client: Any, *, bucket: str, prefix: str) -> bool:
    """Return whether a raw S3 prefix contains at least one object."""

    list_prefix = f"{prefix.strip('/')}/" if prefix.strip("/") else ""
    response = client.list_objects_v2(Bucket=bucket, Prefix=list_prefix, MaxKeys=1)
    return bool(response.get("Contents"))


def _manifest_metadata_summary(manifest: ArtifactManifest) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in _MANIFEST_SUMMARY_KEYS:
        if key in manifest.metadata:
            summary[key] = manifest.metadata[key]
    if manifest.dependencies:
        summary["dependencies"] = [
            dependency.model_dump(mode="json")
            for dependency in manifest.dependencies
        ]
    return _redact(summary)


def _manifest_dataset_match(manifest: ArtifactManifest, spec: DatasetSpec) -> bool:
    metadata = manifest.metadata
    candidates = {
        str(metadata.get("dataset", "")),
        str(metadata.get("dataset_name", "")),
        str(metadata.get("task_name", "")),
        str(metadata.get("dataset_slug", "")),
    }
    if spec.task_name in candidates or spec.slug in candidates:
        return True
    return manifest.artifact_id == spec.slug or manifest.artifact_id.startswith(f"{spec.slug}_")


def inventory_corpus_assets(
    *,
    store: ArtifactStore,
    raw_client: Any,
    bucket: str,
    raw_prefix: str,
    datasets: list[DatasetSpec] | None = None,
) -> dict[str, Any]:
    """Inventory raw prefixes and corpus/index artifacts for target datasets."""

    selected = datasets or list(TARGET_DATASETS)
    artifact_manifests: dict[str, list[ArtifactManifest]] = {}
    for artifact_type in ARTIFACT_STAGE_ORDER:
        manifests: list[ArtifactManifest] = []
        for _current_type, artifact_id in store.list_artifacts(artifact_type):
            try:
                manifests.append(store.read_manifest(artifact_type, artifact_id))
            except Exception:
                # Incomplete or corrupt manifests are represented through the artifact record.
                manifests.append(
                    ArtifactManifest(
                        artifact_id=artifact_id,
                        artifact_type=artifact_type,
                        created_at=datetime.fromtimestamp(0, tz=UTC),
                        metadata={"manifest_read_error": True},
                    )
                )
        artifact_manifests[artifact_type] = manifests

    dataset_results: dict[str, Any] = {}
    for spec in selected:
        prefix_key = raw_prefix_key(raw_prefix, spec)
        raw_exists = raw_prefix_exists(raw_client, bucket=bucket, prefix=prefix_key)
        artifacts_by_type: dict[str, list[dict[str, Any]]] = {}
        missing: list[str] = []

        for artifact_type in ARTIFACT_STAGE_ORDER:
            records: list[dict[str, Any]] = []
            for manifest in artifact_manifests.get(artifact_type, []):
                if not _manifest_dataset_match(manifest, spec):
                    continue
                complete = store.is_complete(artifact_type, manifest.artifact_id)
                records.append(
                    {
                        "artifact_id": manifest.artifact_id,
                        "complete": complete,
                        "has_manifest": not manifest.metadata.get("manifest_read_error", False),
                        "has_success": store.exists(
                            artifact_type,
                            manifest.artifact_id,
                            SUCCESS_MARKER,
                        ),
                        "artifact_uri": store.artifact_uri(artifact_type, manifest.artifact_id),
                        "metadata_summary": _manifest_metadata_summary(manifest),
                    }
                )
            artifacts_by_type[artifact_type] = sorted(
                records,
                key=lambda item: str(item["artifact_id"]),
            )
            if not any(record["complete"] for record in records):
                missing.append(artifact_type)

        if not raw_exists:
            missing.insert(0, "raw_prefix")

        dataset_results[spec.task_name] = {
            "slug": spec.slug,
            "raw_format": spec.raw_format,
            "raw_prefix": s3_uri(bucket, prefix_key),
            "raw_prefix_exists": raw_exists,
            "expected_raw_files": list(spec.expected_raw_files),
            "artifacts": artifacts_by_type,
            "missing": missing,
        }

    return {
        "datasets": dataset_results,
        "artifact_stage_order": ARTIFACT_STAGE_ORDER,
    }


def build_plan_for_datasets(
    *,
    datasets: list[DatasetSpec],
    run_id: str,
    bucket: str,
    raw_prefix: str,
    s3_prefix: str,
    raw_exists_by_slug: dict[str, bool],
    reuse_existing: bool = False,
    inventory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a dry-run plan for corpus/index artifacts."""

    dataset_plans: dict[str, Any] = {}
    for spec in datasets:
        if not raw_exists_by_slug.get(spec.slug, False):
            raise CorpusAssetError(f"Raw prefix does not exist for {spec.task_name}")

        generated_artifact_ids = artifact_ids_for_dataset(spec, run_id)
        resolved_artifact_ids: dict[str, str] = {}
        steps: list[dict[str, Any]] = []
        source_artifact_id: str | None = None

        for artifact_type in ARTIFACT_STAGE_ORDER:
            artifact_id = generated_artifact_ids[artifact_type]
            action = "create"
            if reuse_existing and inventory is not None:
                existing = _first_complete_inventory_artifact(
                    inventory,
                    spec.task_name,
                    artifact_type,
                )
                if existing is not None:
                    artifact_id = str(existing["artifact_id"])
                    action = "reuse"
            resolved_artifact_ids[artifact_type] = artifact_id

            step: dict[str, Any] = {
                "stage": artifact_type,
                "action": action,
                "artifact_type": artifact_type,
                "artifact_id": artifact_id,
                "artifact_uri": s3_uri(bucket, s3_prefix, artifact_type, artifact_id),
            }
            if source_artifact_id is not None:
                step["source_artifact_id"] = source_artifact_id
            if artifact_type == "raw_dataset":
                step["raw_source_uri"] = raw_prefix_uri(bucket, raw_prefix, spec)
            if artifact_type == "elasticsearch_index":
                step["index_name"] = index_name_for_dataset(spec, run_id)
                step["source_artifact_id"] = resolved_artifact_ids["chunked_corpus"]
            if artifact_type == "milvus_collection":
                step.pop("source_artifact_id", None)
                step["collection_name"] = collection_name_for_dataset(spec, run_id)
                step["chunked_corpus_artifact_id"] = resolved_artifact_ids["chunked_corpus"]
                step["embeddings_artifact_id"] = resolved_artifact_ids["embeddings"]
            steps.append(step)
            source_artifact_id = artifact_id

        dataset_plans[spec.task_name] = {
            "slug": spec.slug,
            "raw_format": spec.raw_format,
            "artifact_ids": generated_artifact_ids,
            "generated_artifact_ids": generated_artifact_ids,
            "resolved_artifact_ids": resolved_artifact_ids,
            "elasticsearch_index_name": index_name_for_dataset(spec, run_id),
            "milvus_collection_name": collection_name_for_dataset(spec, run_id),
            "steps": steps,
        }

    return {
        "mode": "dry_run",
        "run_id": run_id,
        "s3_prefix": s3_prefix,
        "reuse_existing": reuse_existing,
        "datasets": dataset_plans,
    }


def _first_complete_inventory_artifact(
    inventory: dict[str, Any],
    task_name: str,
    artifact_type: str,
) -> dict[str, Any] | None:
    dataset = inventory.get("datasets", {}).get(task_name, {})
    for record in dataset.get("artifacts", {}).get(artifact_type, []):
        if record.get("complete"):
            return record
    return None


def load_config_and_client(config_path: Path) -> tuple[PlatformConfig, Any]:
    """Load platform config and create an S3 client."""

    config = load_platform_config(config_path)
    return config, make_s3_client(config)


def output_payload(payload: dict[str, Any], output: Path | None) -> None:
    """Print JSON and optionally write it to a local file."""

    text = safe_json_dumps(payload)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")


def add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add shared config/S3 arguments."""

    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--s3-prefix", default="test_sciverse_benchmark")
    parser.add_argument("--raw-prefix", default="sciverse_benchmark/raw")
    parser.add_argument("--output", type=Path, default=None)


def redacted_config_summary(config: PlatformConfig) -> dict[str, Any]:
    """Return a safe config summary for reports."""

    return dump_redacted_config(config)
