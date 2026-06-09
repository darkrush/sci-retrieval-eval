"""Expected corpus asset fingerprint helpers."""

from __future__ import annotations

from typing import Any

from eval_platform.artifacts.metadata_keys import METADATA_KEY_ASSET_FINGERPRINT_SHA256
from eval_platform.artifacts.types import (
    NORMALIZED_DATASET_ARTIFACT_TYPE,
    RAW_DATASET_ARTIFACT_TYPE,
)
from eval_platform.assets import (
    build_asset_fingerprint,
    normalized_dataset_fingerprint_components,
)
from eval_platform.corpus_assets.registry import CorpusAssetError, DatasetSpec
from eval_platform.datasets.raw_normalize import RAW_NORMALIZER_SPECS


def build_expected_asset_fingerprints_by_slug(
    *,
    config: Any,
    datasets: list[DatasetSpec],
    inventory: dict[str, Any],
    explicit_expected_asset_fingerprints_by_slug: (
        dict[str, dict[str, str]] | None
    ) = None,
) -> dict[str, dict[str, str]]:
    """Build expected corpus asset fingerprints for dry-run reuse decisions.

    The corpus asset planner only knows how to filter existing inventory records
    by expected fingerprints. This helper derives those expectations from the
    current dataset registry and platform config, then lets explicit user values
    override the automatic defaults.
    """

    del config  # Reserved for chunking/embedding/index expectations in later stages.
    explicit = explicit_expected_asset_fingerprints_by_slug or {}
    result: dict[str, dict[str, str]] = {}
    for spec in datasets:
        automatic = _automatic_expected_fingerprints_for_dataset(
            spec,
            inventory=inventory,
        )
        explicit_for_dataset = dict(
            explicit.get(spec.slug) or explicit.get(spec.task_name) or {}
        )
        merged = {**automatic, **explicit_for_dataset}
        if merged:
            result[spec.slug] = merged
    return result


def _automatic_expected_fingerprints_for_dataset(
    spec: DatasetSpec,
    *,
    inventory: dict[str, Any],
) -> dict[str, str]:
    raw_fingerprint = _latest_complete_raw_fingerprint(spec, inventory)
    if raw_fingerprint is None:
        return {}

    expected: dict[str, str] = {
        RAW_DATASET_ARTIFACT_TYPE: raw_fingerprint,
    }
    expected[NORMALIZED_DATASET_ARTIFACT_TYPE] = _normalized_fingerprint(
        spec,
        raw_fingerprint=raw_fingerprint,
    )
    return expected


def _latest_complete_raw_fingerprint(
    spec: DatasetSpec,
    inventory: dict[str, Any],
) -> str | None:
    dataset_inventory = inventory.get("datasets", {}).get(spec.task_name, {})
    records = dataset_inventory.get("artifacts", {}).get(RAW_DATASET_ARTIFACT_TYPE, [])
    complete_records = [
        record
        for record in records
        if record.get("complete") and _record_asset_fingerprint(record) is not None
    ]
    if not complete_records:
        return None
    selected = sorted(
        complete_records,
        key=lambda record: str(record.get("artifact_id") or ""),
        reverse=True,
    )[0]
    return _record_asset_fingerprint(selected)


def _record_asset_fingerprint(record: dict[str, Any]) -> str | None:
    metadata = record.get("metadata_summary", {})
    value = metadata.get(METADATA_KEY_ASSET_FINGERPRINT_SHA256)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _normalized_fingerprint(spec: DatasetSpec, *, raw_fingerprint: str) -> str:
    normalizer_spec = RAW_NORMALIZER_SPECS.get(spec.task_name)
    if normalizer_spec is None:
        raise CorpusAssetError(f"No raw normalizer spec registered for {spec.task_name!r}")

    normalizer_params: dict[str, Any] = {
        "split": "test",
        "raw_format": normalizer_spec.raw_format,
        "has_instructions": normalizer_spec.has_instructions,
    }
    if normalizer_spec.query_text_policy is not None:
        normalizer_params["query_text_policy"] = normalizer_spec.query_text_policy

    return build_asset_fingerprint(
        artifact_type=NORMALIZED_DATASET_ARTIFACT_TYPE,
        components=normalized_dataset_fingerprint_components(
            raw_dataset_fingerprint=raw_fingerprint,
            normalizer_name=normalizer_spec.normalizer_name,
            normalizer_version="1",
            schema_version="1",
            normalizer_params=normalizer_params,
        ),
    ).sha256
