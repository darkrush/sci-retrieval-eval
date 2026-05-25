"""Tests for chunking runner orchestration."""

from __future__ import annotations

import subprocess
from collections.abc import Iterable
from pathlib import Path

import pytest

from eval_platform.artifacts import LocalArtifactStore
from eval_platform.chunking import CHUNKED_CORPUS_ARTIFACT_TYPE, ChunkRecord, run_chunking
from eval_platform.chunking.git import GitRepoDirtyError
from eval_platform.chunking.runner import ChunkingRunConfig, ExternalChunker
from eval_platform.datasets import (
    CorpusRecord,
    NormalizedDataset,
    QueryRecord,
    write_normalized_dataset_artifact,
)


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    return True


pytestmark = pytest.mark.skipif(not _git_available(), reason="git not available")


def _run_git(repo_path: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo_path, check=True, capture_output=True)


def _init_git_repo(repo_path: Path) -> None:
    _run_git(repo_path, "init")
    _run_git(repo_path, "config", "user.name", "test-user")
    _run_git(repo_path, "config", "user.email", "test@example.com")
    (repo_path / "README.md").write_text("initial\n", encoding="utf-8")
    _run_git(repo_path, "add", "README.md")
    _run_git(repo_path, "commit", "-m", "initial")


def _git_head(repo_path: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class FakeChunker:
    """In-memory chunker used for runner tests."""

    def __init__(self) -> None:
        self.call_count = 0

    def chunk_corpus(self, dataset: NormalizedDataset) -> Iterable[ChunkRecord]:
        self.call_count += 1
        return [
            ChunkRecord(
                chunk_id=f"{doc.doc_id}-0",
                doc_id=doc.doc_id,
                text=f"chunk from {doc.doc_id}",
                chunk_index=0,
            )
            for doc in dataset.corpus
        ]


@pytest.fixture
def store(tmp_path: Path) -> LocalArtifactStore:
    return LocalArtifactStore(tmp_path)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "chunker-repo"
    repo_path.mkdir()
    _init_git_repo(repo_path)
    return repo_path


@pytest.fixture
def source_artifact_id(store: LocalArtifactStore) -> str:
    artifact_id = "litsearch_test"
    dataset = NormalizedDataset(
        corpus=[
            CorpusRecord(doc_id="doc-1", text="first document"),
            CorpusRecord(doc_id="doc-2", text="second document"),
        ],
        queries=[QueryRecord(query_id="q-1", text="query")],
        qrels=[],
        metadata={"source": "unit-test"},
    )
    write_normalized_dataset_artifact(store, artifact_id, dataset)
    return artifact_id


def test_run_chunking_writes_chunked_corpus_artifact(
    store: LocalArtifactStore,
    git_repo: Path,
    source_artifact_id: str,
) -> None:
    config = ChunkingRunConfig(
        source_artifact_id=source_artifact_id,
        output_artifact_id="litsearch_test_chunks",
        chunker_name="fake-chunker",
        chunker_repo_path=str(git_repo),
        chunk_params={"max_tokens": 512},
    )

    manifest = run_chunking(store, config, FakeChunker())

    assert manifest.artifact_id == "litsearch_test_chunks"
    assert store.is_complete(CHUNKED_CORPUS_ARTIFACT_TYPE, "litsearch_test_chunks") is True


def test_run_chunking_records_source_dependency(
    store: LocalArtifactStore,
    git_repo: Path,
    source_artifact_id: str,
) -> None:
    config = ChunkingRunConfig(
        source_artifact_id=source_artifact_id,
        output_artifact_id="litsearch_test_chunks",
        chunker_name="fake-chunker",
        chunker_repo_path=str(git_repo),
    )

    manifest = run_chunking(store, config, FakeChunker())

    assert len(manifest.dependencies) == 1
    assert manifest.dependencies[0].artifact_id == source_artifact_id
    assert manifest.dependencies[0].artifact_type == "normalized_dataset"


def test_run_chunking_records_chunker_provenance(
    store: LocalArtifactStore,
    git_repo: Path,
    source_artifact_id: str,
) -> None:
    config = ChunkingRunConfig(
        source_artifact_id=source_artifact_id,
        output_artifact_id="litsearch_test_chunks",
        chunker_name="fake-chunker",
        chunker_repo_path=str(git_repo),
        chunk_params={"max_tokens": 512, "overlap": 64},
    )

    manifest = run_chunking(store, config, FakeChunker())
    chunker = manifest.metadata["chunker"]

    assert chunker["name"] == "fake-chunker"
    assert chunker["commit_sha"] == _git_head(git_repo)
    assert chunker["is_dirty"] is False
    assert manifest.metadata["chunk_params"] == {"max_tokens": 512, "overlap": 64}


def test_run_chunking_raises_for_dirty_chunker_repo(
    store: LocalArtifactStore,
    git_repo: Path,
    source_artifact_id: str,
) -> None:
    (git_repo / "README.md").write_text("modified\n", encoding="utf-8")
    config = ChunkingRunConfig(
        source_artifact_id=source_artifact_id,
        output_artifact_id="litsearch_test_chunks",
        chunker_name="fake-chunker",
        chunker_repo_path=str(git_repo),
    )

    with pytest.raises(GitRepoDirtyError):
        run_chunking(store, config, FakeChunker())


def test_run_chunking_calls_fake_chunker_once(
    store: LocalArtifactStore,
    git_repo: Path,
    source_artifact_id: str,
) -> None:
    chunker = FakeChunker()
    config = ChunkingRunConfig(
        source_artifact_id=source_artifact_id,
        output_artifact_id="litsearch_test_chunks",
        chunker_name="fake-chunker",
        chunker_repo_path=str(git_repo),
    )

    run_chunking(store, config, chunker)

    assert chunker.call_count == 1


def test_external_chunker_protocol_is_structural() -> None:
    chunker = FakeChunker()

    assert isinstance(chunker, ExternalChunker)
