"""Tests for real corpus asset build dry-run planning."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS_ROOT = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from corpus_asset_common import (  # noqa: E402, I001
    ARTIFACT_STAGE_ORDER,
    CorpusAssetError,
    DATASETS_BY_NAME,
    build_plan_for_datasets,
    dataset_specs_for_selection,
)


def test_dataset_selection_supports_task_name_slug_and_all() -> None:
    assert [spec.task_name for spec in dataset_specs_for_selection("IFIRNFCorpus")] == [
        "IFIRNFCorpus"
    ]
    assert [spec.task_name for spec in dataset_specs_for_selection("ifir_nfcorpus")] == [
        "IFIRNFCorpus"
    ]
    assert len(dataset_specs_for_selection("all")) == 5


def test_build_plan_orders_stages_and_uses_stable_names() -> None:
    spec = DATASETS_BY_NAME["IFIRNFCorpus"]

    plan = build_plan_for_datasets(
        datasets=[spec],
        run_id="five_ds_001",
        bucket="bucket",
        raw_prefix="sciverse_benchmark/raw",
        s3_prefix="test_sciverse_benchmark",
        raw_exists_by_slug={"ifir_nfcorpus": True},
    )

    dataset_plan = plan["datasets"]["IFIRNFCorpus"]
    assert [step["stage"] for step in dataset_plan["steps"]] == ARTIFACT_STAGE_ORDER
    assert dataset_plan["artifact_ids"]["raw_dataset"] == "ifir_nfcorpus_five_ds_001_raw"
    assert dataset_plan["artifact_ids"]["elasticsearch_index"] == (
        "ifir_nfcorpus_five_ds_001_es_index"
    )
    assert dataset_plan["elasticsearch_index_name"] == "ifir_nfcorpus_five_ds_001_es"
    assert dataset_plan["milvus_collection_name"] == "ifir_nfcorpus_five_ds_001_milvus"
    assert dataset_plan["steps"][0]["raw_source_uri"] == (
        "s3://bucket/sciverse_benchmark/raw/ifir_nfcorpus"
    )
    assert dataset_plan["steps"][4]["source_artifact_id"] == (
        "ifir_nfcorpus_five_ds_001_chunks"
    )
    assert dataset_plan["steps"][5]["chunked_corpus_artifact_id"] == (
        "ifir_nfcorpus_five_ds_001_chunks"
    )
    assert dataset_plan["steps"][5]["embeddings_artifact_id"] == (
        "ifir_nfcorpus_five_ds_001_embeddings"
    )
    assert "source_artifact_id" not in dataset_plan["steps"][5]


def test_build_plan_raises_when_raw_prefix_missing() -> None:
    with pytest.raises(CorpusAssetError, match="Raw prefix does not exist"):
        build_plan_for_datasets(
            datasets=[DATASETS_BY_NAME["SciFact"]],
            run_id="five_ds_001",
            bucket="bucket",
            raw_prefix="sciverse_benchmark/raw",
            s3_prefix="test_sciverse_benchmark",
            raw_exists_by_slug={"scifact": False},
        )


def test_build_plan_can_reuse_existing_complete_artifacts() -> None:
    spec = DATASETS_BY_NAME["NFCorpus"]
    inventory: dict[str, Any] = {
        "datasets": {
            "NFCorpus": {
                "artifacts": {
                    "raw_dataset": [
                        {"artifact_id": "nfcorpus_old_raw", "complete": True}
                    ],
                    "normalized_dataset": [],
                    "chunked_corpus": [],
                    "embeddings": [],
                    "elasticsearch_index": [],
                    "milvus_collection": [],
                }
            }
        }
    }

    plan = build_plan_for_datasets(
        datasets=[spec],
        run_id="five_ds_001",
        bucket="bucket",
        raw_prefix="sciverse_benchmark/raw",
        s3_prefix="test_sciverse_benchmark",
        raw_exists_by_slug={"nfcorpus": True},
        reuse_existing=True,
        inventory=inventory,
    )

    first_step = plan["datasets"]["NFCorpus"]["steps"][0]
    assert first_step["action"] == "reuse"
    assert first_step["artifact_id"] == "nfcorpus_old_raw"


def test_build_plan_is_dry_run_and_has_no_external_clients() -> None:
    plan = build_plan_for_datasets(
        datasets=[DATASETS_BY_NAME["LitSearchRetrieval"]],
        run_id="five_ds_001",
        bucket="bucket",
        raw_prefix="sciverse_benchmark/raw",
        s3_prefix="test_sciverse_benchmark",
        raw_exists_by_slug={"litsearch": True},
    )

    assert plan["mode"] == "dry_run"
    for step in plan["datasets"]["LitSearchRetrieval"]["steps"]:
        assert step["action"] == "create"
        assert "client" not in step
        assert "api_key" not in step
        assert "password" not in step
