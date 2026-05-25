"""Offline smoke test for IFIRNFCorpus normalized + fake chunk artifacts.

Run with:
python -m eval_platform.cli.ifir_nfcorpus_smoke
"""

from __future__ import annotations

import csv
import json
import subprocess
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer

from eval_platform.artifacts import LocalArtifactStore
from eval_platform.chunking import (
    ChunkRecord,
    ChunkingRunConfig,
    read_chunked_corpus_artifact,
    run_chunking,
)
from eval_platform.datasets import (
    CorpusRecord,
    NormalizedDataset,
    QrelRecord,
    QueryRecord,
    read_normalized_dataset_artifact,
    write_normalized_dataset_artifact,
)

app = typer.Typer(help="Run IFIRNFCorpus local artifact smoke test.")

REPO_ROOT = Path(__file__).resolve().parents[3]
SCI_BASE_ROOT = REPO_ROOT.parent
DEFAULT_SOURCE_DIR = SCI_BASE_ROOT / "bench_assets" / "ifir_nfcorpus_raw"
DEFAULT_LOCAL_ROOT = REPO_ROOT / ".local_artifacts" / "test"


@dataclass
class ArtifactSummary:
    artifact_id: str
    complete: bool
    manifest_path: str
    payload_path: str
    counts: dict[str, int]


class FakeSmokeChunker:
    """Very small fake chunker for smoke validation."""

    def chunk_corpus(self, dataset: NormalizedDataset) -> Iterable[ChunkRecord]:
        for doc in dataset.corpus:
            yield ChunkRecord(
                chunk_id=f"{doc.doc_id}-fake-0",
                doc_id=doc.doc_id,
                title=doc.title,
                text=doc.text[:1000],
                chunk_index=0,
                metadata={"fake_smoke_chunker": True},
            )


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _repo_short_sha(repo_root: Path) -> str:
    return _run_git(["rev-parse", "--short", "HEAD"], cwd=repo_root)


def _default_run_id(repo_root: Path) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{_repo_short_sha(repo_root)}"


def _load_corpus(path: Path) -> list[CorpusRecord]:
    records: list[CorpusRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            records.append(
                CorpusRecord(
                    doc_id=str(row["_id"]),
                    title=row.get("title"),
                    text=str(row["text"]),
                )
            )
    return records


def _load_queries(path: Path) -> list[QueryRecord]:
    records: list[QueryRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            records.append(QueryRecord(query_id=str(row["_id"]), text=str(row["text"])))
    return records


def _load_qrels(path: Path) -> list[QrelRecord]:
    records: list[QrelRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            records.append(
                QrelRecord(
                    query_id=str(row["query-id"]),
                    doc_id=str(row["corpus-id"]),
                    relevance=float(row["score"]),
                )
            )
    return records


def _build_dataset(source_dir: Path) -> NormalizedDataset:
    corpus = _load_corpus(source_dir / "corpus.jsonl")
    queries = _load_queries(source_dir / "queries.jsonl")
    qrels = _load_qrels(source_dir / "qrels_test.tsv")
    return NormalizedDataset(
        corpus=corpus,
        queries=queries,
        qrels=qrels,
        metadata={
            "source": "offline_ifir_nfcorpus_raw",
            "task_name": "IFIRNFCorpus",
            "split": "test",
        },
    )


def _ensure_fake_chunker_repo(repo_dir: Path) -> None:
    repo_dir.mkdir(parents=True, exist_ok=True)
    readme = repo_dir / "README.md"
    if not readme.exists():
        readme.write_text("fake smoke chunker\n", encoding="utf-8")

    if not (repo_dir / ".git").exists():
        _run_git(["init"], cwd=repo_dir)
        _run_git(["config", "user.name", "codex-smoke"], cwd=repo_dir)
        _run_git(["config", "user.email", "codex-smoke@example.com"], cwd=repo_dir)
        _run_git(["add", "README.md"], cwd=repo_dir)
        _run_git(["commit", "-m", "init fake smoke chunker"], cwd=repo_dir)


def _inspection_commands(
    local_root: Path,
    normalized_artifact_id: str,
    fake_chunked_artifact_id: str,
) -> list[str]:
    root = local_root.as_posix()
    return [
        f"find {root} -maxdepth 5 -type f | sort",
        (
            "cat "
            f"{root}/normalized_dataset/{normalized_artifact_id}/_MANIFEST.json"
        ),
        (
            "head -n 3 "
            f"{root}/normalized_dataset/{normalized_artifact_id}/corpus.jsonl"
        ),
        (
            "head -n 3 "
            f"{root}/normalized_dataset/{normalized_artifact_id}/queries.jsonl"
        ),
        (
            "head -n 3 "
            f"{root}/normalized_dataset/{normalized_artifact_id}/qrels.jsonl"
        ),
        (
            "cat "
            f"{root}/chunked_corpus/{fake_chunked_artifact_id}/_MANIFEST.json"
        ),
        (
            "head -n 5 "
            f"{root}/chunked_corpus/{fake_chunked_artifact_id}/chunks.jsonl"
        ),
    ]


def _cleanup_commands(local_root: Path) -> list[str]:
    return [f"rm -rf {local_root.as_posix()}"]


@app.command()
def main(
    run_id: str | None = typer.Option(None, help="Optional fixed run id."),
    source_dir: Path = typer.Option(
        DEFAULT_SOURCE_DIR,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="IFIRNFCorpus raw asset directory.",
    ),
    local_root_base: Path = typer.Option(
        DEFAULT_LOCAL_ROOT,
        file_okay=False,
        dir_okay=True,
        writable=True,
        help="Base directory for test artifacts.",
    ),
) -> None:
    smoke_run_id = run_id or _default_run_id(REPO_ROOT)
    local_root = local_root_base / smoke_run_id
    store = LocalArtifactStore(local_root)

    normalized_artifact_id = f"test_mteb_ifirnfcorpus_test_{smoke_run_id}"
    fake_chunked_artifact_id = f"{normalized_artifact_id}_fake_chunks"

    dataset = _build_dataset(source_dir)
    normalized_manifest = write_normalized_dataset_artifact(
        store,
        normalized_artifact_id,
        dataset,
        created_by="codex-integration-smoke",
        metadata={
            "test_run": True,
            "run_id": smoke_run_id,
            "stage": "offline_ifirnfcorpus_to_normalized_local",
        },
    )
    normalized = read_normalized_dataset_artifact(store, normalized_artifact_id)

    fake_repo_dir = local_root / "fake_chunker_repo"
    _ensure_fake_chunker_repo(fake_repo_dir)

    fake_chunk_manifest = run_chunking(
        store,
        ChunkingRunConfig(
            source_artifact_id=normalized_artifact_id,
            output_artifact_id=fake_chunked_artifact_id,
            chunker_name="fake-smoke-chunker",
            chunker_repo_path=str(fake_repo_dir),
            chunk_params={"mode": "first_1000_chars", "test_run": True},
            created_by="codex-integration-smoke",
            metadata={"test_run": True, "run_id": smoke_run_id},
        ),
        FakeSmokeChunker(),
    )
    fake_chunked = read_chunked_corpus_artifact(store, fake_chunked_artifact_id)

    normalized_summary = ArtifactSummary(
        artifact_id=normalized_artifact_id,
        complete=store.is_complete("normalized_dataset", normalized_artifact_id),
        manifest_path=str(local_root / "normalized_dataset" / normalized_artifact_id / "_MANIFEST.json"),
        payload_path=str(local_root / "normalized_dataset" / normalized_artifact_id),
        counts={
            "corpus": len(normalized.corpus),
            "queries": len(normalized.queries),
            "qrels": len(normalized.qrels),
        },
    )
    fake_summary = ArtifactSummary(
        artifact_id=fake_chunked_artifact_id,
        complete=store.is_complete("chunked_corpus", fake_chunked_artifact_id),
        manifest_path=str(local_root / "chunked_corpus" / fake_chunked_artifact_id / "_MANIFEST.json"),
        payload_path=str(local_root / "chunked_corpus" / fake_chunked_artifact_id),
        counts={"chunks": len(fake_chunked.chunks)},
    )

    result: dict[str, Any] = {
        "run_id": smoke_run_id,
        "repo_head": _repo_short_sha(REPO_ROOT),
        "source_dir": str(source_dir),
        "local_root": str(local_root),
        "normalized_dataset": asdict(normalized_summary),
        "normalized_manifest": normalized_manifest.model_dump(mode="json"),
        "fake_chunked_corpus": asdict(fake_summary),
        "fake_chunked_manifest": fake_chunk_manifest.model_dump(mode="json"),
        "inspection_commands": _inspection_commands(
            local_root, normalized_artifact_id, fake_chunked_artifact_id
        ),
        "cleanup_commands": _cleanup_commands(local_root),
        "notes": [
            "This smoke uses offline IFIRNFCorpus raw assets, not mteb.load_data().",
            "No embedding was run.",
            "No ES or Milvus index was created.",
            "No retrieval or metrics were run.",
        ],
    }
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
