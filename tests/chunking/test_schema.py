"""Tests for chunking schema models."""

import pytest
from pydantic import ValidationError

from eval_platform.chunking import ChunkerProvenance


def test_chunker_provenance_construction() -> None:
    provenance = ChunkerProvenance(
        name="sciverse-chunker",
        repo_url="https://example.com/sciverse-chunker.git",
        repo_path="/tmp/sciverse-chunker",
        commit_sha="abc123def456",
        branch="main",
        is_dirty=True,
        metadata={"runtime": "test"},
    )

    assert provenance.name == "sciverse-chunker"
    assert provenance.commit_sha == "abc123def456"
    assert provenance.is_dirty is True
    assert provenance.metadata == {"runtime": "test"}


@pytest.mark.parametrize("name", ["", " "])
def test_chunker_provenance_rejects_empty_name(name: str) -> None:
    with pytest.raises(ValidationError):
        ChunkerProvenance(name=name, commit_sha="abc123")


@pytest.mark.parametrize("commit_sha", ["", " "])
def test_chunker_provenance_rejects_empty_commit_sha(commit_sha: str) -> None:
    with pytest.raises(ValidationError):
        ChunkerProvenance(name="sciverse-chunker", commit_sha=commit_sha)


def test_chunker_provenance_is_dirty_defaults_to_false() -> None:
    provenance = ChunkerProvenance(name="sciverse-chunker", commit_sha="abc123")

    assert provenance.is_dirty is False


def test_chunker_provenance_metadata_defaults_are_independent() -> None:
    first = ChunkerProvenance(name="chunker-a", commit_sha="abc123")
    second = ChunkerProvenance(name="chunker-b", commit_sha="def456")

    first.metadata["key"] = "a"
    second.metadata["key"] = "b"

    assert first.metadata == {"key": "a"}
    assert second.metadata == {"key": "b"}
