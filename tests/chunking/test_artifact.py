"""Tests for chunked corpus artifact helpers."""

from pathlib import Path

import pytest

from eval_platform.artifacts import LocalArtifactStore
from eval_platform.chunking import (
    ChunkedCorpus,
    ChunkerProvenance,
    ChunkRecord,
    write_chunked_corpus_artifact,
)


@pytest.fixture
def store(tmp_path: Path) -> LocalArtifactStore:
    return LocalArtifactStore(tmp_path)


def _sample_corpus() -> ChunkedCorpus:
    return ChunkedCorpus(
        chunks=[
            ChunkRecord(chunk_id="c-1", doc_id="doc-1", text="first chunk", chunk_index=0),
            ChunkRecord(chunk_id="c-2", doc_id="doc-1", text="second chunk", chunk_index=1),
            ChunkRecord(chunk_id="c-3", doc_id="doc-2", text="other doc", chunk_index=0),
        ],
        metadata={"source_normalized_dataset_artifact_id": "litsearch_test"},
    )


def test_write_chunked_corpus_artifact_records_chunker_provenance(
    store: LocalArtifactStore,
) -> None:
    chunker = ChunkerProvenance(
        name="sciverse-chunker",
        repo_url="https://example.com/sciverse-chunker.git",
        commit_sha="deadbeef123456",
        branch="main",
    )

    manifest = write_chunked_corpus_artifact(
        store,
        "litsearch_test",
        _sample_corpus(),
        chunker=chunker,
    )

    assert "chunker" in manifest.metadata
    assert manifest.metadata["chunker"]["commit_sha"] == "deadbeef123456"
    assert manifest.metadata["chunker"]["name"] == "sciverse-chunker"


def test_write_chunked_corpus_artifact_records_chunk_params(store: LocalArtifactStore) -> None:
    manifest = write_chunked_corpus_artifact(
        store,
        "litsearch_test",
        _sample_corpus(),
        chunk_params={"max_tokens": 512, "overlap": 64},
    )

    assert manifest.metadata["chunk_params"] == {"max_tokens": 512, "overlap": 64}


def test_manifest_count_metadata_is_not_overridden_by_user_metadata(
    store: LocalArtifactStore,
) -> None:
    manifest = write_chunked_corpus_artifact(
        store,
        "litsearch_test",
        _sample_corpus(),
        metadata={
            "chunk_count": 999,
            "unique_doc_count": 888,
            "pipeline_step": "chunk",
        },
    )

    assert manifest.metadata["chunk_count"] == 3
    assert manifest.metadata["unique_doc_count"] == 2
    assert manifest.metadata["pipeline_step"] == "chunk"


def test_write_chunked_corpus_artifact_marks_complete(store: LocalArtifactStore) -> None:
    manifest = write_chunked_corpus_artifact(store, "litsearch_test", _sample_corpus())

    assert store.is_complete("chunked_corpus", manifest.artifact_id) is True
