"""Tests for raw dataset artifact helpers."""

from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime
from pathlib import Path

import pytest

from eval_platform.artifacts import (
    ArtifactIncompleteError,
    ArtifactManifest,
    LocalArtifactStore,
    S3ArtifactStore,
)
from eval_platform.datasets import (
    RAW_DATASET_ARTIFACT_TYPE,
    RAW_DATASET_FILES_DIR,
    RawDatasetFile,
    RawDatasetSnapshot,
    build_content_fingerprint_sha256,
    import_raw_dataset_from_local_dir,
    import_raw_dataset_from_s3_prefix,
    read_raw_dataset_artifact,
    write_raw_dataset_artifact,
)


class FakeS3Client:
    def __init__(self, page_size: int | None = None) -> None:
        self.objects: dict[str, bytes] = {}
        self.page_size = page_size

    def _full_key(self, bucket: str, key: str) -> str:
        return f"{bucket}/{key}"

    def put_object(self, *, Bucket: str, Key: str, Body: bytes | io.BytesIO) -> None:
        data = Body.read() if hasattr(Body, "read") else Body
        self.objects[self._full_key(Bucket, Key)] = data

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, io.BytesIO]:
        return {"Body": io.BytesIO(self.objects[self._full_key(Bucket, Key)])}

    def head_object(self, *, Bucket: str, Key: str) -> None:
        if self._full_key(Bucket, Key) not in self.objects:
            raise KeyError(Key)

    def list_objects_v2(
        self,
        *,
        Bucket: str,
        Prefix: str = "",
        ContinuationToken: str | None = None,
    ) -> dict[str, object]:
        matching_keys = sorted(
            key[len(f"{Bucket}/") :]
            for key in self.objects
            if key.startswith(f"{Bucket}/") and key[len(f"{Bucket}/") :].startswith(Prefix)
        )
        page_size = self.page_size or len(matching_keys)
        start = int(ContinuationToken) if ContinuationToken else 0
        page_keys = matching_keys[start : start + page_size]
        next_start = start + page_size
        is_truncated = next_start < len(matching_keys)
        return {
            "Contents": [{"Key": key} for key in page_keys],
            "IsTruncated": is_truncated,
            "NextContinuationToken": str(next_start) if is_truncated else None,
        }


@pytest.fixture
def store(tmp_path: Path) -> LocalArtifactStore:
    return LocalArtifactStore(tmp_path)


def _payload_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sample_snapshot() -> tuple[RawDatasetSnapshot, dict[str, bytes]]:
    payloads = {
        "corpus/a.jsonl": b'{"id": 1}\n',
        "corpus/b.jsonl": b'{"id": 2}\n',
    }
    files = [
        RawDatasetFile(
            path=path,
            size_bytes=len(payload),
            sha256=_payload_sha256(payload),
        )
        for path, payload in sorted(payloads.items())
    ]
    return (
        RawDatasetSnapshot(
            source_type="local_dir",
            source_uri="file:///tmp/raw",
            dataset_name="sample-dataset",
            dataset_revision="r1",
            files=files,
            content_fingerprint_sha256=build_content_fingerprint_sha256(files),
            import_parameters={"pattern": "*.jsonl"},
            metadata={"owner": "unit-test"},
        ),
        payloads,
    )


def test_write_raw_dataset_artifact_writes_files(store: LocalArtifactStore) -> None:
    snapshot, payloads = _sample_snapshot()

    write_raw_dataset_artifact(store, "sample_001", snapshot, payloads)

    assert store.exists(RAW_DATASET_ARTIFACT_TYPE, "sample_001", "files/corpus/a.jsonl")
    assert store.exists(RAW_DATASET_ARTIFACT_TYPE, "sample_001", "files/corpus/b.jsonl")


def test_write_raw_dataset_artifact_marks_complete(store: LocalArtifactStore) -> None:
    snapshot, payloads = _sample_snapshot()

    write_raw_dataset_artifact(store, "sample_001", snapshot, payloads)

    assert store.is_complete(RAW_DATASET_ARTIFACT_TYPE, "sample_001") is True


def test_read_raw_dataset_artifact_round_trip_metadata(store: LocalArtifactStore) -> None:
    snapshot, payloads = _sample_snapshot()

    write_raw_dataset_artifact(store, "sample_001", snapshot, payloads)
    loaded = read_raw_dataset_artifact(store, "sample_001")

    assert loaded == snapshot


def test_manifest_metadata_contains_required_fields(store: LocalArtifactStore) -> None:
    snapshot, payloads = _sample_snapshot()

    manifest = write_raw_dataset_artifact(
        store,
        "sample_001",
        snapshot,
        payloads,
        metadata={"stage": "wrong", "file_count": 999, "note": "kept"},
    )

    assert manifest.metadata["stage"] == "raw_dataset"
    assert manifest.metadata["source_type"] == "local_dir"
    assert manifest.metadata["source_uri"] == "file:///tmp/raw"
    assert manifest.metadata["dataset_name"] == "sample-dataset"
    assert manifest.metadata["dataset_revision"] == "r1"
    assert manifest.metadata["file_count"] == 2
    assert manifest.metadata["total_size_bytes"] == sum(
        len(payload) for payload in payloads.values()
    )
    assert manifest.metadata["content_fingerprint_sha256"] == snapshot.content_fingerprint_sha256
    assert manifest.metadata["import_parameters"] == {"pattern": "*.jsonl"}
    assert manifest.metadata["note"] == "kept"
    assert [item["path"] for item in manifest.metadata["files"]] == [
        "corpus/a.jsonl",
        "corpus/b.jsonl",
    ]


def test_manifest_files_record_artifact_paths(store: LocalArtifactStore) -> None:
    snapshot, payloads = _sample_snapshot()

    manifest = write_raw_dataset_artifact(store, "sample_001", snapshot, payloads)

    assert {file.path for file in manifest.files} == {
        f"{RAW_DATASET_FILES_DIR}/corpus/a.jsonl",
        f"{RAW_DATASET_FILES_DIR}/corpus/b.jsonl",
    }


def test_read_requires_complete_artifact(store: LocalArtifactStore) -> None:
    snapshot, payloads = _sample_snapshot()
    artifact_id = "sample_001"

    for path, payload in payloads.items():
        store.put_file(
            RAW_DATASET_ARTIFACT_TYPE,
            artifact_id,
            f"{RAW_DATASET_FILES_DIR}/{path}",
            payload,
        )

    store.write_manifest(
        RAW_DATASET_ARTIFACT_TYPE,
        artifact_id,
        ArtifactManifest(
            artifact_id=artifact_id,
            artifact_type=RAW_DATASET_ARTIFACT_TYPE,
            created_at=datetime(2026, 5, 26, 12, 0, 0, tzinfo=UTC),
            metadata={
                "stage": "raw_dataset",
                "source_type": snapshot.source_type,
                "source_uri": snapshot.source_uri,
                "dataset_name": snapshot.dataset_name,
                "dataset_revision": snapshot.dataset_revision,
                "file_count": 2,
                "total_size_bytes": sum(len(payload) for payload in payloads.values()),
                "files": [file.model_dump(mode="json") for file in snapshot.files],
                "content_fingerprint_sha256": snapshot.content_fingerprint_sha256,
                "import_parameters": snapshot.import_parameters,
            },
        ),
    )

    with pytest.raises(ArtifactIncompleteError):
        read_raw_dataset_artifact(store, artifact_id)


def test_import_raw_dataset_from_local_dir_builds_snapshot(
    store: LocalArtifactStore, tmp_path: Path
) -> None:
    source_dir = tmp_path / "source"
    (source_dir / "nested").mkdir(parents=True)
    (source_dir / "a.txt").write_bytes(b"alpha")
    (source_dir / "nested" / "b.bin").write_bytes(b"beta")

    manifest = import_raw_dataset_from_local_dir(
        store,
        "raw_local_001",
        source_dir,
        dataset_name="demo-local",
        dataset_revision="2026-05-26",
        import_parameters={"source_split": "train"},
        metadata={"team": "search"},
    )
    loaded = read_raw_dataset_artifact(store, "raw_local_001")

    assert manifest.metadata["stage"] == "raw_dataset"
    assert manifest.metadata["source_type"] == "local_dir"
    assert manifest.metadata["dataset_name"] == "demo-local"
    assert manifest.metadata["file_count"] == 2
    assert manifest.metadata["total_size_bytes"] == 9
    assert [file.path for file in loaded.files] == ["a.txt", "nested/b.bin"]
    assert loaded.metadata == {"team": "search"}
    assert store.get_file(RAW_DATASET_ARTIFACT_TYPE, "raw_local_001", "files/a.txt") == b"alpha"


def test_import_raw_dataset_from_s3_prefix_to_local_store(
    store: LocalArtifactStore,
) -> None:
    client = FakeS3Client()
    client.put_object(Bucket="raw-bucket", Key="incoming/raw/a.jsonl", Body=b"a")
    client.put_object(Bucket="raw-bucket", Key="incoming/raw/nested/b.jsonl", Body=b"bb")

    manifest = import_raw_dataset_from_s3_prefix(
        store,
        "raw_s3_001",
        client=client,
        bucket="raw-bucket",
        prefix="incoming/raw",
        dataset_name="demo-s3",
        import_parameters={"compression": "none"},
    )
    loaded = read_raw_dataset_artifact(store, "raw_s3_001")

    assert manifest.metadata["source_type"] == "s3_prefix"
    assert manifest.metadata["source_uri"] == "s3://raw-bucket/incoming/raw"
    assert manifest.metadata["file_count"] == 2
    assert [file.path for file in loaded.files] == ["a.jsonl", "nested/b.jsonl"]
    assert store.get_file(RAW_DATASET_ARTIFACT_TYPE, "raw_s3_001", "files/nested/b.jsonl") == b"bb"


def test_import_raw_dataset_can_write_to_s3_store(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "a.txt").write_bytes(b"payload")

    client = FakeS3Client()
    store = S3ArtifactStore(bucket="test-bucket", prefix="eval-artifacts/dev", client=client)

    import_raw_dataset_from_local_dir(
        store,
        "raw_s3_output_001",
        source_dir,
        dataset_name="demo-output",
    )

    assert store.is_complete(RAW_DATASET_ARTIFACT_TYPE, "raw_s3_output_001") is True
    loaded = read_raw_dataset_artifact(store, "raw_s3_output_001")
    assert loaded.dataset_name == "demo-output"
