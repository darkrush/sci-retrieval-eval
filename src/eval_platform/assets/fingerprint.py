"""Asset fingerprint schemas and component builders."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field, ValidationInfo, field_validator

SECRET_KEY_FRAGMENTS = (
    "api_key",
    "access_key",
    "secret",
    "password",
    "token",
    "authorization",
)
OPERATIONAL_IDENTITY_KEYS = frozenset(
    {
        "artifact_id",
        "created_at",
        "created_by",
        "run_id",
    }
)


class AssetFingerprintError(Exception):
    """Raised when an asset fingerprint payload is unsafe or invalid."""


class AssetFingerprint(BaseModel):
    """Stable logical identity for an asset."""

    fingerprint_version: int = Field(default=1, ge=1)
    artifact_type: str
    components: dict[str, Any] = Field(default_factory=dict)
    sha256: str

    @field_validator("artifact_type", "sha256")
    @classmethod
    def validate_non_empty_string(cls, value: str, info: ValidationInfo) -> str:
        field_name = info.field_name or "field"
        if not value.strip():
            raise ValueError(f"{field_name} must not be empty")
        return value


def canonical_json_hash(payload: Mapping[str, Any]) -> str:
    """Return a sha256 hex digest for a canonical JSON mapping."""

    normalized_payload = _normalize_mapping(payload, "payload")
    try:
        canonical = json.dumps(
            normalized_payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise AssetFingerprintError(
            f"Asset fingerprint payload is not JSON-serializable: {exc}"
        ) from exc
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_asset_fingerprint(
    *,
    artifact_type: str,
    components: Mapping[str, Any],
    fingerprint_version: int = 1,
) -> AssetFingerprint:
    """Build an asset fingerprint without mutating the input components."""

    component_copy = _normalize_mapping(components, "components")
    payload = {
        "fingerprint_version": fingerprint_version,
        "artifact_type": artifact_type,
        "components": component_copy,
    }
    sha256 = canonical_json_hash(payload)
    return AssetFingerprint(
        fingerprint_version=fingerprint_version,
        artifact_type=artifact_type,
        components=component_copy,
        sha256=sha256,
    )


def assert_no_secret_keys(payload: Mapping[str, Any]) -> None:
    """Reject mappings containing secret-like keys at any nested level."""

    _assert_no_secret_keys(payload, path="payload")


def raw_dataset_fingerprint_components(
    *,
    dataset_name: str,
    raw_source_uri: str,
    raw_format: str,
    split: str | None = None,
    file_fingerprints: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build fingerprint components for a raw dataset snapshot."""

    components = {
        "dataset_name": _require_non_empty(dataset_name, "dataset_name"),
        "raw_source_uri": _require_non_empty(raw_source_uri, "raw_source_uri"),
        "raw_format": _require_non_empty(raw_format, "raw_format"),
        "split": _optional_non_empty(split, "split"),
        "file_fingerprints": _normalize_optional_mapping_sequence(
            file_fingerprints,
            "file_fingerprints",
        ),
    }
    assert_no_secret_keys(components)
    return components


def normalized_dataset_fingerprint_components(
    *,
    raw_dataset_fingerprint: str,
    normalizer_name: str,
    normalizer_version: str,
    schema_version: str,
    normalizer_params: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build fingerprint components for a normalized dataset."""

    components = {
        "raw_dataset_fingerprint": _require_non_empty(
            raw_dataset_fingerprint,
            "raw_dataset_fingerprint",
        ),
        "normalizer_name": _require_non_empty(normalizer_name, "normalizer_name"),
        "normalizer_version": _require_non_empty(
            normalizer_version,
            "normalizer_version",
        ),
        "schema_version": _require_non_empty(schema_version, "schema_version"),
        "normalizer_params": _normalize_optional_mapping(
            normalizer_params,
            "normalizer_params",
        ),
    }
    assert_no_secret_keys(components)
    return components


def chunked_corpus_fingerprint_components(
    *,
    normalized_dataset_fingerprint: str,
    chunker_name: str,
    chunker_commit_sha: str,
    chunk_params: Mapping[str, Any],
    schema_version: str,
    chunker_repo_url: str | None = None,
) -> dict[str, Any]:
    """Build fingerprint components for a chunked corpus."""

    components = {
        "normalized_dataset_fingerprint": _require_non_empty(
            normalized_dataset_fingerprint,
            "normalized_dataset_fingerprint",
        ),
        "chunker_name": _require_non_empty(chunker_name, "chunker_name"),
        "chunker_commit_sha": _require_non_empty(
            chunker_commit_sha,
            "chunker_commit_sha",
        ),
        "chunker_repo_url": _optional_non_empty(chunker_repo_url, "chunker_repo_url"),
        "chunk_params": _normalize_mapping(chunk_params, "chunk_params"),
        "schema_version": _require_non_empty(schema_version, "schema_version"),
    }
    assert_no_secret_keys(components)
    return components


def embeddings_fingerprint_components(
    *,
    chunked_corpus_fingerprint: str,
    model_name: str,
    embedding_dim: int,
    provider: str | None = None,
    endpoint_alias: str | None = None,
    api_version: str | None = None,
    normalized: bool | None = None,
    preprocessing: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build fingerprint components for chunk embeddings."""

    if embedding_dim <= 0:
        raise AssetFingerprintError("embedding_dim must be greater than 0")
    components = {
        "chunked_corpus_fingerprint": _require_non_empty(
            chunked_corpus_fingerprint,
            "chunked_corpus_fingerprint",
        ),
        "model_name": _require_non_empty(model_name, "model_name"),
        "embedding_dim": embedding_dim,
        "provider": _optional_non_empty(provider, "provider"),
        "endpoint_alias": _optional_non_empty(endpoint_alias, "endpoint_alias"),
        "api_version": _optional_non_empty(api_version, "api_version"),
        "normalized": normalized,
        "preprocessing": _normalize_optional_mapping(preprocessing, "preprocessing"),
    }
    assert_no_secret_keys(components)
    return components


def elasticsearch_index_fingerprint_components(
    *,
    chunked_corpus_fingerprint: str,
    mapping: Mapping[str, Any],
    analyzer: Mapping[str, Any] | None = None,
    ingest_params: Mapping[str, Any] | None = None,
    builder_version: str,
) -> dict[str, Any]:
    """Build fingerprint components for an Elasticsearch index."""

    components = {
        "chunked_corpus_fingerprint": _require_non_empty(
            chunked_corpus_fingerprint,
            "chunked_corpus_fingerprint",
        ),
        "mapping": _normalize_mapping(mapping, "mapping"),
        "analyzer": _normalize_optional_mapping(analyzer, "analyzer"),
        "ingest_params": _normalize_optional_mapping(ingest_params, "ingest_params"),
        "builder_version": _require_non_empty(builder_version, "builder_version"),
    }
    assert_no_secret_keys(components)
    return components


def milvus_collection_fingerprint_components(
    *,
    chunked_corpus_fingerprint: str,
    embeddings_fingerprint: str,
    schema: Mapping[str, Any],
    metric_type: str,
    index_type: str,
    index_params: Mapping[str, Any],
    builder_version: str,
) -> dict[str, Any]:
    """Build fingerprint components for a Milvus collection."""

    components = {
        "chunked_corpus_fingerprint": _require_non_empty(
            chunked_corpus_fingerprint,
            "chunked_corpus_fingerprint",
        ),
        "embeddings_fingerprint": _require_non_empty(
            embeddings_fingerprint,
            "embeddings_fingerprint",
        ),
        "schema": _normalize_mapping(schema, "schema"),
        "metric_type": _require_non_empty(metric_type, "metric_type"),
        "index_type": _require_non_empty(index_type, "index_type"),
        "index_params": _normalize_mapping(index_params, "index_params"),
        "builder_version": _require_non_empty(builder_version, "builder_version"),
    }
    assert_no_secret_keys(components)
    return components


def retrieval_run_fingerprint_components(
    *,
    normalized_dataset_fingerprint: str,
    retrieval_mode: str,
    retrieval_params: Mapping[str, Any],
    elasticsearch_index_fingerprint: str | None = None,
    milvus_collection_fingerprint: str | None = None,
    embedding_query_fingerprint: str | None = None,
    rerank_fingerprint: str | None = None,
    rewrite_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Build fingerprint components for a retrieval run."""

    components = {
        "normalized_dataset_fingerprint": _require_non_empty(
            normalized_dataset_fingerprint,
            "normalized_dataset_fingerprint",
        ),
        "retrieval_mode": _require_non_empty(retrieval_mode, "retrieval_mode"),
        "retrieval_params": _normalize_mapping(retrieval_params, "retrieval_params"),
        "elasticsearch_index_fingerprint": _optional_non_empty(
            elasticsearch_index_fingerprint,
            "elasticsearch_index_fingerprint",
        ),
        "milvus_collection_fingerprint": _optional_non_empty(
            milvus_collection_fingerprint,
            "milvus_collection_fingerprint",
        ),
        "embedding_query_fingerprint": _optional_non_empty(
            embedding_query_fingerprint,
            "embedding_query_fingerprint",
        ),
        "rerank_fingerprint": _optional_non_empty(
            rerank_fingerprint,
            "rerank_fingerprint",
        ),
        "rewrite_fingerprint": _optional_non_empty(
            rewrite_fingerprint,
            "rewrite_fingerprint",
        ),
    }
    assert_no_secret_keys(components)
    return components


def metrics_run_fingerprint_components(
    *,
    normalized_dataset_fingerprint: str,
    retrieval_run_fingerprint: str,
    metric_params: Mapping[str, Any],
) -> dict[str, Any]:
    """Build fingerprint components for a metrics run."""

    components = {
        "normalized_dataset_fingerprint": _require_non_empty(
            normalized_dataset_fingerprint,
            "normalized_dataset_fingerprint",
        ),
        "retrieval_run_fingerprint": _require_non_empty(
            retrieval_run_fingerprint,
            "retrieval_run_fingerprint",
        ),
        "metric_params": _normalize_mapping(metric_params, "metric_params"),
    }
    assert_no_secret_keys(components)
    return components


def _require_non_empty(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise AssetFingerprintError(f"{field_name} must be a string")
    if not value.strip():
        raise AssetFingerprintError(f"{field_name} must not be empty")
    return value


def _optional_non_empty(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_non_empty(value, field_name)


def _normalize_optional_mapping(
    payload: Mapping[str, Any] | None,
    field_name: str,
) -> dict[str, Any] | None:
    if payload is None:
        return None
    return _normalize_mapping(payload, field_name)


def _normalize_mapping(payload: Mapping[str, Any], field_name: str) -> dict[str, Any]:
    assert_no_secret_keys(payload)
    _assert_no_operational_identity_keys(payload, path=field_name)
    normalized = _normalize_json_value(payload, field_name)
    if not isinstance(normalized, dict):
        raise AssetFingerprintError(f"{field_name} must be a JSON object")
    return normalized


def _normalize_optional_mapping_sequence(
    values: Sequence[Mapping[str, Any]] | None,
    field_name: str,
) -> list[dict[str, Any]] | None:
    if values is None:
        return None
    if isinstance(values, (str, bytes)):
        raise AssetFingerprintError(f"{field_name} must be a sequence of mappings")
    return [
        _normalize_mapping(value, f"{field_name}[{index}]")
        for index, value in enumerate(values)
    ]


def _assert_no_secret_keys(value: Any, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_path = f"{path}.{key}"
            if isinstance(key, str):
                key_lower = key.lower()
                if any(fragment in key_lower for fragment in SECRET_KEY_FRAGMENTS):
                    raise AssetFingerprintError(
                        f"Asset fingerprint payload contains secret-like key: {key_path}"
                    )
            _assert_no_secret_keys(child, key_path)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            _assert_no_secret_keys(child, f"{path}[{index}]")


def _assert_no_operational_identity_keys(value: Any, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_path = f"{path}.{key}"
            if isinstance(key, str) and key.lower() in OPERATIONAL_IDENTITY_KEYS:
                raise AssetFingerprintError(
                    f"Asset fingerprint payload contains operational identity key: {key_path}"
                )
            _assert_no_operational_identity_keys(child, key_path)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            _assert_no_operational_identity_keys(child, f"{path}[{index}]")


def _normalize_json_value(value: Any, path: str) -> Any:
    if value is None or isinstance(value, str | bool | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise AssetFingerprintError(f"{path} must be a finite JSON number")
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise AssetFingerprintError(f"{path} contains a non-string key: {key!r}")
            normalized[key] = _normalize_json_value(child, f"{path}.{key}")
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [
            _normalize_json_value(child, f"{path}[{index}]")
            for index, child in enumerate(value)
        ]
    raise AssetFingerprintError(
        f"{path} contains a non-JSON-serializable value of type {type(value).__name__}"
    )
