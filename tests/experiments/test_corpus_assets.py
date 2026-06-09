"""Tests for experiment corpus asset resolution."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from eval_platform.experiments import corpus_assets as corpus_asset_module
from eval_platform.experiments.schema import ExperimentCorpusAssetConfig


def test_experiment_resolution_passes_auto_expected_fingerprints(
    monkeypatch,
) -> None:
    spec = SimpleNamespace(slug="ifir_nfcorpus", task_name="IFIRNFCorpus")
    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        corpus_asset_module,
        "dataset_specs_for_selection",
        lambda selection: [spec],
    )
    monkeypatch.setattr(
        corpus_asset_module,
        "inventory_corpus_assets",
        lambda **kwargs: {"datasets": {"IFIRNFCorpus": {}}},
    )
    monkeypatch.setattr(
        corpus_asset_module,
        "build_expected_asset_fingerprints_by_slug",
        lambda **kwargs: {
            "ifir_nfcorpus": {
                "raw_dataset": "raw-fp",
                "normalized_dataset": "normalized-fp",
            }
        },
    )
    monkeypatch.setattr(
        corpus_asset_module,
        "build_plan_for_datasets",
        lambda **kwargs: captured.update(kwargs) or {"datasets": {}},
    )
    monkeypatch.setattr(
        corpus_asset_module,
        "benchmark_dataset_specs_from_corpus_asset_plan",
        lambda plan, required_artifact_types: [],
    )

    _, plan = corpus_asset_module.resolve_benchmark_datasets_from_corpus_assets(
        cast(Any, SimpleNamespace()),
        ExperimentCorpusAssetConfig(
            dataset_selection="IFIRNFCorpus",
            corpus_run_id="run-1",
            bucket="bucket",
            s3_prefix="prefix",
        ),
    )

    assert plan == {"datasets": {}}
    assert captured["expected_asset_fingerprints_by_slug"] == {
        "ifir_nfcorpus": {
            "raw_dataset": "raw-fp",
            "normalized_dataset": "normalized-fp",
        }
    }
