"""Tests for the narrow IFIRNFCorpus corpus asset executor."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from eval_platform.artifacts import ArtifactManifest, LocalArtifactStore
from eval_platform.artifacts.types import (
    CHUNKED_CORPUS_ARTIFACT_TYPE,
    ELASTICSEARCH_INDEX_ARTIFACT_TYPE,
    EMBEDDINGS_ARTIFACT_TYPE,
    MILVUS_COLLECTION_ARTIFACT_TYPE,
)
from eval_platform.datasets import (
    CorpusRecord,
    NormalizedDataset,
    QrelRecord,
    QueryRecord,
    write_normalized_dataset_artifact,
)

SCRIPTS_ROOT = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import execute_ifir_nfcorpus_corpus_assets as execute_script  # noqa: E402


def test_validate_args_rejects_non_ifir_dataset() -> None:
    with pytest.raises(execute_script.IFIRCorpusAssetExecuteError, match="Only"):
        execute_script._validate_args(
            argparse.Namespace(
                dataset="NFCorpus",
                s3_prefix="sciverse_benchmark/assets",
                run_id="run",
            )
        )


def test_validate_args_rejects_test_prefix() -> None:
    with pytest.raises(execute_script.IFIRCorpusAssetExecuteError, match="test_"):
        execute_script._validate_args(
            argparse.Namespace(
                dataset="IFIRNFCorpus",
                s3_prefix="test_sciverse_benchmark/assets",
                run_id="run",
            )
        )


def test_run_builds_plan_before_refusing_without_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = SimpleNamespace(s3=SimpleNamespace(bucket="bucket"))
    client = object()
    store = object()
    spec = SimpleNamespace(slug="ifir_nfcorpus", task_name="IFIRNFCorpus")
    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        execute_script,
        "load_config_and_client",
        lambda path: (config, client),
    )
    monkeypatch.setattr(
        execute_script,
        "dataset_specs_for_selection",
        lambda selection: [spec],
    )
    monkeypatch.setattr(
        execute_script,
        "make_s3_artifact_store",
        lambda *, config, s3_prefix, client: store,
    )
    monkeypatch.setattr(
        execute_script,
        "inventory_corpus_assets",
        lambda **kwargs: {"datasets": {"IFIRNFCorpus": {}}},
    )
    monkeypatch.setattr(
        execute_script,
        "build_expected_asset_fingerprints_by_slug",
        lambda **kwargs: {"ifir_nfcorpus": {"normalized_dataset": "expected"}},
    )
    monkeypatch.setattr(execute_script, "raw_prefix_key", lambda raw_prefix, spec: "raw/key")
    monkeypatch.setattr(execute_script, "raw_prefix_exists", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        execute_script,
        "build_plan_for_datasets",
        lambda **kwargs: {"mode": "dry_run", "datasets": {"IFIRNFCorpus": {}}},
    )
    monkeypatch.setattr(
        execute_script,
        "output_payload",
        lambda payload, output: captured.update(payload=payload, output=output),
    )

    with pytest.raises(execute_script.IFIRCorpusAssetExecuteError, match="without --yes"):
        execute_script.run(
            argparse.Namespace(
                config=Path("config.yaml"),
                s3_prefix="sciverse_benchmark/assets",
                raw_prefix="sciverse_benchmark/raw",
                run_id="run",
                dataset="IFIRNFCorpus",
                reuse_existing=True,
                yes=False,
                output=None,
            )
        )

    assert captured["payload"]["kind"] == "ifir_nfcorpus_corpus_asset_execute_plan"
    assert captured["payload"]["execute"] is False


def test_validate_ifir_normalized_artifact_rejects_old_query_policy(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    write_normalized_dataset_artifact(
        store,
        "old_ifir_normalized",
        NormalizedDataset(
            corpus=[CorpusRecord(doc_id="d1", text="doc")],
            queries=[
                QueryRecord(
                    query_id="q1",
                    text="plain query",
                    metadata={"instruction": "plain query instruction"},
                )
            ],
            qrels=[QrelRecord(query_id="q1", doc_id="d1", relevance=1.0)],
        ),
        metadata={"task_name": "IFIRNFCorpus"},
    )

    with pytest.raises(execute_script.IFIRCorpusAssetExecuteError, match="missing"):
        execute_script.validate_ifir_normalized_artifact(store, "old_ifir_normalized")


def test_preflight_rejects_missing_chunking_config() -> None:
    config = SimpleNamespace(
        chunking=SimpleNamespace(repo_path=None, repo_remote=None, commit_sha=None),
        embedding=SimpleNamespace(model="BAAI/bge-m3", dim=1024, endpoints=[]),
        elasticsearch=SimpleNamespace(url="http://es"),
        milvus=SimpleNamespace(address="tcp://milvus:19530"),
    )
    plan = {
        "datasets": {
            "IFIRNFCorpus": {
                "steps": [
                    {"artifact_type": CHUNKED_CORPUS_ARTIFACT_TYPE, "action": "create"}
                ]
            }
        }
    }

    with pytest.raises(execute_script.IFIRCorpusAssetExecuteError, match="chunking"):
        execute_script._preflight_create_stages(cast(Any, config), plan)


def test_validate_ifir_normalized_artifact_accepts_effective_query(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    write_normalized_dataset_artifact(
        store,
        "new_ifir_normalized",
        NormalizedDataset(
            corpus=[CorpusRecord(doc_id="d1", text="doc")],
            queries=[
                QueryRecord(
                    query_id="q1",
                    text="plain query instruction",
                    metadata={
                        "source_query_text": "plain query",
                        "instruction": "instruction",
                        "effective_query_text": "plain query instruction",
                        "query_text_policy": "mteb_text_plus_instruction",
                        "instruction_startswith_query_text": False,
                    },
                )
            ],
            qrels=[QrelRecord(query_id="q1", doc_id="d1", relevance=1.0)],
        ),
        metadata={
            "task_name": "IFIRNFCorpus",
            "query_text_policy": "mteb_text_plus_instruction",
        },
    )

    execute_script.validate_ifir_normalized_artifact(store, "new_ifir_normalized")


def test_validate_ingest_manifests_rejects_count_mismatch(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    artifact_ids = {
        CHUNKED_CORPUS_ARTIFACT_TYPE: "chunks",
        EMBEDDINGS_ARTIFACT_TYPE: "embeddings",
        ELASTICSEARCH_INDEX_ARTIFACT_TYPE: "es",
        MILVUS_COLLECTION_ARTIFACT_TYPE: "milvus",
    }
    _write_manifest(store, CHUNKED_CORPUS_ARTIFACT_TYPE, "chunks", {"chunk_count": 2})
    _write_manifest(store, EMBEDDINGS_ARTIFACT_TYPE, "embeddings", {"embedding_count": 2})
    _write_manifest(
        store,
        ELASTICSEARCH_INDEX_ARTIFACT_TYPE,
        "es",
        {"index_name": "idx", "verified_document_count": 1},
    )
    _write_manifest(
        store,
        MILVUS_COLLECTION_ARTIFACT_TYPE,
        "milvus",
        {"collection_name": "coll", "verified_entity_count": 2},
    )

    with pytest.raises(execute_script.IFIRCorpusAssetExecuteError, match="ES"):
        execute_script.validate_ingest_manifests(store, artifact_ids)


def _write_manifest(
    store: LocalArtifactStore,
    artifact_type: str,
    artifact_id: str,
    metadata: dict[str, Any],
) -> None:
    store.write_manifest(
        artifact_type,
        artifact_id,
        ArtifactManifest(
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            created_at=datetime.now(UTC),
            metadata=metadata,
        ),
    )
    store.mark_success(artifact_type, artifact_id)
