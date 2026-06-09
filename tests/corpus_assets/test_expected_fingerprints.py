"""Tests for corpus asset expected fingerprint generation."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from eval_platform.artifacts.types import (
    NORMALIZED_DATASET_ARTIFACT_TYPE,
    RAW_DATASET_ARTIFACT_TYPE,
)
from eval_platform.assets import (
    build_asset_fingerprint,
    normalized_dataset_fingerprint_components,
)
from eval_platform.corpus_assets import (
    DATASETS_BY_NAME,
    build_expected_asset_fingerprints_by_slug,
)


def _inventory(task_name: str, raw_fingerprint: str) -> dict[str, Any]:
    return {
        "datasets": {
            task_name: {
                "artifacts": {
                    RAW_DATASET_ARTIFACT_TYPE: [
                        {
                            "artifact_id": f"{task_name.lower()}_raw",
                            "complete": True,
                            "metadata_summary": {
                                "asset_fingerprint_sha256": raw_fingerprint,
                            },
                        }
                    ],
                }
            }
        }
    }


def test_ifir_expected_normalized_fingerprint_includes_query_text_policy() -> None:
    spec = DATASETS_BY_NAME["IFIRNFCorpus"]
    raw_fingerprint = "raw-ifir-fp"

    expected = build_expected_asset_fingerprints_by_slug(
        config=SimpleNamespace(),
        datasets=[spec],
        inventory=_inventory("IFIRNFCorpus", raw_fingerprint),
    )

    manual = build_asset_fingerprint(
        artifact_type=NORMALIZED_DATASET_ARTIFACT_TYPE,
        components=normalized_dataset_fingerprint_components(
            raw_dataset_fingerprint=raw_fingerprint,
            normalizer_name="ifir_nfcorpus_raw_jsonl_tsv_v1",
            normalizer_version="1",
            schema_version="1",
            normalizer_params={
                "split": "test",
                "raw_format": "jsonl_tsv",
                "has_instructions": True,
                "query_text_policy": "mteb_text_plus_instruction",
            },
        ),
    ).sha256
    without_policy = build_asset_fingerprint(
        artifact_type=NORMALIZED_DATASET_ARTIFACT_TYPE,
        components=normalized_dataset_fingerprint_components(
            raw_dataset_fingerprint=raw_fingerprint,
            normalizer_name="ifir_nfcorpus_raw_jsonl_tsv_v1",
            normalizer_version="1",
            schema_version="1",
            normalizer_params={
                "split": "test",
                "raw_format": "jsonl_tsv",
                "has_instructions": True,
            },
        ),
    ).sha256

    assert expected[spec.slug][RAW_DATASET_ARTIFACT_TYPE] == raw_fingerprint
    assert expected[spec.slug][NORMALIZED_DATASET_ARTIFACT_TYPE] == manual
    assert expected[spec.slug][NORMALIZED_DATASET_ARTIFACT_TYPE] != without_policy


def test_non_ifir_expected_normalized_fingerprint_does_not_add_ifir_policy() -> None:
    spec = DATASETS_BY_NAME["NFCorpus"]
    raw_fingerprint = "raw-nfcorpus-fp"

    expected = build_expected_asset_fingerprints_by_slug(
        config=SimpleNamespace(),
        datasets=[spec],
        inventory=_inventory("NFCorpus", raw_fingerprint),
    )

    manual = build_asset_fingerprint(
        artifact_type=NORMALIZED_DATASET_ARTIFACT_TYPE,
        components=normalized_dataset_fingerprint_components(
            raw_dataset_fingerprint=raw_fingerprint,
            normalizer_name="nfcorpus_raw_jsonl_tsv_v1",
            normalizer_version="1",
            schema_version="1",
            normalizer_params={
                "split": "test",
                "raw_format": "jsonl_tsv",
                "has_instructions": False,
            },
        ),
    ).sha256

    assert expected[spec.slug][NORMALIZED_DATASET_ARTIFACT_TYPE] == manual


def test_explicit_expected_fingerprints_override_automatic_values() -> None:
    spec = DATASETS_BY_NAME["IFIRNFCorpus"]

    expected = build_expected_asset_fingerprints_by_slug(
        config=SimpleNamespace(),
        datasets=[spec],
        inventory=_inventory("IFIRNFCorpus", "raw-auto"),
        explicit_expected_asset_fingerprints_by_slug={
            "ifir_nfcorpus": {
                NORMALIZED_DATASET_ARTIFACT_TYPE: "explicit-normalized",
            }
        },
    )

    assert expected[spec.slug][RAW_DATASET_ARTIFACT_TYPE] == "raw-auto"
    assert expected[spec.slug][NORMALIZED_DATASET_ARTIFACT_TYPE] == (
        "explicit-normalized"
    )
