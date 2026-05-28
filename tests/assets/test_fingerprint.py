from __future__ import annotations

import pytest
from pydantic import ValidationError

from eval_platform.assets import (
    AssetFingerprintError,
    build_asset_fingerprint,
    canonical_json_hash,
    chunked_corpus_fingerprint_components,
    elasticsearch_index_fingerprint_components,
    embeddings_fingerprint_components,
    metrics_run_fingerprint_components,
    milvus_collection_fingerprint_components,
    normalized_dataset_fingerprint_components,
    raw_dataset_fingerprint_components,
    retrieval_run_fingerprint_components,
)


def test_canonical_hash_is_stable_for_key_order() -> None:
    first = {"b": 2, "a": {"y": 1, "x": [3, 4]}}
    second = {"a": {"x": [3, 4], "y": 1}, "b": 2}

    assert canonical_json_hash(first) == canonical_json_hash(second)


def test_canonical_hash_changes_for_different_value() -> None:
    first = {"a": 1}
    second = {"a": 2}

    assert canonical_json_hash(first) != canonical_json_hash(second)


def test_canonical_hash_rejects_non_json_serializable_value() -> None:
    with pytest.raises(AssetFingerprintError):
        canonical_json_hash({"bad": object()})


def test_canonical_hash_rejects_secret_key() -> None:
    with pytest.raises(AssetFingerprintError):
        canonical_json_hash({"api_key": "redacted"})


def test_canonical_hash_rejects_nested_secret_key() -> None:
    with pytest.raises(AssetFingerprintError):
        canonical_json_hash({"embedding": {"Access_Key": "redacted"}})


def test_canonical_hash_rejects_secret_key_inside_list_of_dicts() -> None:
    with pytest.raises(AssetFingerprintError):
        canonical_json_hash({"files": [{"path": "a"}, {"token": "redacted"}]})


def test_canonical_hash_rejects_operational_identity_key() -> None:
    with pytest.raises(AssetFingerprintError):
        canonical_json_hash({"run_id": "experiment-001"})


def test_build_asset_fingerprint_returns_stable_fingerprint() -> None:
    components = {"model": "demo", "params": {"top_k": 10}}

    first = build_asset_fingerprint(artifact_type="retrieval_run", components=components)
    second = build_asset_fingerprint(
        artifact_type="retrieval_run",
        components={"params": {"top_k": 10}, "model": "demo"},
    )

    assert first.sha256 == second.sha256
    assert first.fingerprint_version == 1
    assert first.artifact_type == "retrieval_run"


def test_build_asset_fingerprint_rejects_empty_artifact_type() -> None:
    with pytest.raises(ValidationError):
        build_asset_fingerprint(artifact_type=" ", components={})


def test_build_asset_fingerprint_rejects_invalid_version() -> None:
    with pytest.raises(ValidationError):
        build_asset_fingerprint(
            artifact_type="retrieval_run",
            components={},
            fingerprint_version=0,
        )


def test_build_asset_fingerprint_does_not_mutate_input_components() -> None:
    components = {"params": {"b": 2, "a": 1}}
    before = {"params": {"b": 2, "a": 1}}

    fingerprint = build_asset_fingerprint(artifact_type="embeddings", components=components)

    assert components == before
    assert fingerprint.components == before
    assert fingerprint.components is not components


def test_raw_dataset_components() -> None:
    components = raw_dataset_fingerprint_components(
        dataset_name="NFCorpus",
        raw_source_uri="s3://bucket/raw/nfcorpus/",
        raw_format="jsonl",
        split="test",
        file_fingerprints=[{"path": "corpus.jsonl", "sha256": "abc"}],
    )

    assert components == {
        "dataset_name": "NFCorpus",
        "raw_source_uri": "s3://bucket/raw/nfcorpus/",
        "raw_format": "jsonl",
        "split": "test",
        "file_fingerprints": [{"path": "corpus.jsonl", "sha256": "abc"}],
    }
    assert "run_id" not in components
    assert "artifact_id" not in components


def test_normalized_dataset_components() -> None:
    components = normalized_dataset_fingerprint_components(
        raw_dataset_fingerprint="raw-sha",
        normalizer_name="mteb",
        normalizer_version="1",
        schema_version="normalized-v1",
        normalizer_params={"doc_id_field": "doc_id"},
    )

    assert components["raw_dataset_fingerprint"] == "raw-sha"
    assert components["normalizer_name"] == "mteb"
    assert components["normalizer_params"] == {"doc_id_field": "doc_id"}


def test_chunked_corpus_components() -> None:
    components = chunked_corpus_fingerprint_components(
        normalized_dataset_fingerprint="normalized-sha",
        chunker_name="sciverse-admin-ingest",
        chunker_commit_sha="abc123",
        chunker_repo_url="https://example.invalid/chunker.git",
        chunk_params={"chunk_size": 512, "overlap": 64},
        schema_version="chunk-v1",
    )

    assert components["normalized_dataset_fingerprint"] == "normalized-sha"
    assert components["chunker_name"] == "sciverse-admin-ingest"
    assert components["chunker_commit_sha"] == "abc123"
    assert components["chunk_params"] == {"chunk_size": 512, "overlap": 64}


def test_embeddings_components() -> None:
    components = embeddings_fingerprint_components(
        chunked_corpus_fingerprint="chunk-sha",
        model_name="bge-large",
        embedding_dim=1024,
        provider="internal",
        endpoint_alias="embedding-prod",
        normalized=True,
        preprocessing={"lowercase": False},
    )

    assert components["chunked_corpus_fingerprint"] == "chunk-sha"
    assert components["model_name"] == "bge-large"
    assert components["provider"] == "internal"
    assert components["embedding_dim"] == 1024


def test_elasticsearch_index_components() -> None:
    components = elasticsearch_index_fingerprint_components(
        chunked_corpus_fingerprint="chunk-sha",
        mapping={"properties": {"text": {"type": "text"}}},
        analyzer={"default": "standard"},
        ingest_params={"refresh": True},
        builder_version="1",
    )

    assert components["chunked_corpus_fingerprint"] == "chunk-sha"
    assert components["mapping"] == {"properties": {"text": {"type": "text"}}}
    assert components["analyzer"] == {"default": "standard"}
    assert components["ingest_params"] == {"refresh": True}


def test_milvus_collection_components() -> None:
    components = milvus_collection_fingerprint_components(
        chunked_corpus_fingerprint="chunk-sha",
        embeddings_fingerprint="embeddings-sha",
        schema={"vector_field": "embedding", "dim": 1024},
        metric_type="IP",
        index_type="HNSW",
        index_params={"M": 16},
        builder_version="1",
    )

    assert components["chunked_corpus_fingerprint"] == "chunk-sha"
    assert components["embeddings_fingerprint"] == "embeddings-sha"
    assert components["schema"] == {"vector_field": "embedding", "dim": 1024}
    assert components["metric_type"] == "IP"
    assert components["index_params"] == {"M": 16}


def test_retrieval_run_components() -> None:
    components = retrieval_run_fingerprint_components(
        normalized_dataset_fingerprint="normalized-sha",
        retrieval_mode="hybrid",
        retrieval_params={"top_k": 10},
        elasticsearch_index_fingerprint="es-sha",
        milvus_collection_fingerprint="milvus-sha",
        embedding_query_fingerprint="query-embedding-sha",
        rerank_fingerprint="rerank-sha",
        rewrite_fingerprint="rewrite-sha",
    )

    assert components["normalized_dataset_fingerprint"] == "normalized-sha"
    assert components["retrieval_mode"] == "hybrid"
    assert components["retrieval_params"] == {"top_k": 10}
    assert components["elasticsearch_index_fingerprint"] == "es-sha"
    assert components["rerank_fingerprint"] == "rerank-sha"
    assert components["rewrite_fingerprint"] == "rewrite-sha"


def test_metrics_run_components() -> None:
    components = metrics_run_fingerprint_components(
        normalized_dataset_fingerprint="normalized-sha",
        retrieval_run_fingerprint="retrieval-sha",
        metric_params={"main_metric": "ndcg_at_10"},
    )

    assert components == {
        "normalized_dataset_fingerprint": "normalized-sha",
        "retrieval_run_fingerprint": "retrieval-sha",
        "metric_params": {"main_metric": "ndcg_at_10"},
    }


def test_changing_embedding_model_changes_embeddings_fingerprint() -> None:
    first = build_asset_fingerprint(
        artifact_type="embeddings",
        components=embeddings_fingerprint_components(
            chunked_corpus_fingerprint="chunk-sha",
            model_name="model-a",
            embedding_dim=768,
        ),
    )
    second = build_asset_fingerprint(
        artifact_type="embeddings",
        components=embeddings_fingerprint_components(
            chunked_corpus_fingerprint="chunk-sha",
            model_name="model-b",
            embedding_dim=768,
        ),
    )

    assert first.sha256 != second.sha256


def test_changing_embedding_model_does_not_change_chunked_corpus_fingerprint() -> None:
    components = chunked_corpus_fingerprint_components(
        normalized_dataset_fingerprint="normalized-sha",
        chunker_name="chunker",
        chunker_commit_sha="abc123",
        chunk_params={"chunk_size": 512},
        schema_version="chunk-v1",
    )

    first = build_asset_fingerprint(artifact_type="chunked_corpus", components=components)
    second = build_asset_fingerprint(artifact_type="chunked_corpus", components=components)

    assert first.sha256 == second.sha256


def test_changing_chunk_params_changes_chunked_corpus_fingerprint() -> None:
    first = build_asset_fingerprint(
        artifact_type="chunked_corpus",
        components=chunked_corpus_fingerprint_components(
            normalized_dataset_fingerprint="normalized-sha",
            chunker_name="chunker",
            chunker_commit_sha="abc123",
            chunk_params={"chunk_size": 512},
            schema_version="chunk-v1",
        ),
    )
    second = build_asset_fingerprint(
        artifact_type="chunked_corpus",
        components=chunked_corpus_fingerprint_components(
            normalized_dataset_fingerprint="normalized-sha",
            chunker_name="chunker",
            chunker_commit_sha="abc123",
            chunk_params={"chunk_size": 1024},
            schema_version="chunk-v1",
        ),
    )

    assert first.sha256 != second.sha256


def test_changing_chunk_params_changes_downstream_embeddings_fingerprint() -> None:
    chunk_a = build_asset_fingerprint(
        artifact_type="chunked_corpus",
        components=chunked_corpus_fingerprint_components(
            normalized_dataset_fingerprint="normalized-sha",
            chunker_name="chunker",
            chunker_commit_sha="abc123",
            chunk_params={"chunk_size": 512},
            schema_version="chunk-v1",
        ),
    )
    chunk_b = build_asset_fingerprint(
        artifact_type="chunked_corpus",
        components=chunked_corpus_fingerprint_components(
            normalized_dataset_fingerprint="normalized-sha",
            chunker_name="chunker",
            chunker_commit_sha="abc123",
            chunk_params={"chunk_size": 1024},
            schema_version="chunk-v1",
        ),
    )
    embeddings_a = build_asset_fingerprint(
        artifact_type="embeddings",
        components=embeddings_fingerprint_components(
            chunked_corpus_fingerprint=chunk_a.sha256,
            model_name="model-a",
            embedding_dim=768,
        ),
    )
    embeddings_b = build_asset_fingerprint(
        artifact_type="embeddings",
        components=embeddings_fingerprint_components(
            chunked_corpus_fingerprint=chunk_b.sha256,
            model_name="model-a",
            embedding_dim=768,
        ),
    )

    assert embeddings_a.sha256 != embeddings_b.sha256


def test_changing_metric_params_changes_metrics_but_not_retrieval_fingerprint() -> None:
    retrieval = build_asset_fingerprint(
        artifact_type="retrieval_run",
        components=retrieval_run_fingerprint_components(
            normalized_dataset_fingerprint="normalized-sha",
            retrieval_mode="hybrid",
            retrieval_params={"top_k": 10},
            elasticsearch_index_fingerprint="es-sha",
            milvus_collection_fingerprint="milvus-sha",
        ),
    )
    metrics_a = build_asset_fingerprint(
        artifact_type="metrics_run",
        components=metrics_run_fingerprint_components(
            normalized_dataset_fingerprint="normalized-sha",
            retrieval_run_fingerprint=retrieval.sha256,
            metric_params={"main_metric": "ndcg_at_10"},
        ),
    )
    metrics_b = build_asset_fingerprint(
        artifact_type="metrics_run",
        components=metrics_run_fingerprint_components(
            normalized_dataset_fingerprint="normalized-sha",
            retrieval_run_fingerprint=retrieval.sha256,
            metric_params={"main_metric": "recall_at_10"},
        ),
    )

    assert metrics_a.sha256 != metrics_b.sha256
    assert retrieval.sha256 == build_asset_fingerprint(
        artifact_type="retrieval_run",
        components=retrieval.components,
    ).sha256
