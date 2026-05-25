"""Real MTEB smoke for IFIRNFCorpus -> normalized -> fake chunked artifacts.

Run with:
python -m eval_platform.cli.mteb_ifir_nfcorpus_smoke
"""

from __future__ import annotations

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
from eval_platform.datasets import read_normalized_dataset_artifact
from eval_platform.mteb_adapter import export_mteb_retrieval_dataset_artifact

app = typer.Typer(help="Run real-MTEB IFIRNFCorpus smoke test.")

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LOCAL_ROOT = REPO_ROOT / ".local_artifacts" / "test"
TASK_NAME = "IFIRNFCorpus"
TASK_SPLIT = "test"


@dataclass
class ArtifactSummary:
    artifact_id: str
    complete: bool
    manifest_path: str
    payload_path: str
    counts: dict[str, int]


class FakeSmokeChunker:
    """Very small fake chunker for smoke validation."""

    def chunk_corpus(self, dataset: Any) -> Iterable[ChunkRecord]:
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
        f"cat {root}/normalized_dataset/{normalized_artifact_id}/_MANIFEST.json",
        f"head -n 3 {root}/normalized_dataset/{normalized_artifact_id}/corpus.jsonl",
        f"head -n 3 {root}/normalized_dataset/{normalized_artifact_id}/queries.jsonl",
        f"head -n 3 {root}/normalized_dataset/{normalized_artifact_id}/qrels.jsonl",
        f"cat {root}/chunked_corpus/{fake_chunked_artifact_id}/_MANIFEST.json",
        f"head -n 5 {root}/chunked_corpus/{fake_chunked_artifact_id}/chunks.jsonl",
    ]


def _cleanup_commands(local_root: Path) -> list[str]:
    return [f"rm -rf {local_root.as_posix()}"]


@app.command()
def main(
    run_id: str | None = typer.Option(None, help="Optional fixed run id."),
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

    typer.echo(f"[1/4] run_id={smoke_run_id}")
    typer.echo(f"[2/4] exporting real MTEB task {TASK_NAME}/{TASK_SPLIT} -> normalized_dataset")
    normalized_manifest = export_mteb_retrieval_dataset_artifact(
        store,
        task_name=TASK_NAME,
        split=TASK_SPLIT,
        artifact_id=normalized_artifact_id,
        created_by="codex-integration-smoke",
        metadata={
            "test_run": True,
            "run_id": smoke_run_id,
            "stage": "real_mteb_to_normalized_local",
        },
    )
    typer.echo("[2/4] normalized_dataset export finished, reading artifact back")
    normalized = read_normalized_dataset_artifact(store, normalized_artifact_id)

    fake_repo_dir = local_root / "fake_chunker_repo"
    typer.echo(f"[3/4] preparing fake chunker repo: {fake_repo_dir}")
    _ensure_fake_chunker_repo(fake_repo_dir)

    typer.echo("[4/4] running fake chunker -> chunked_corpus")
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
    typer.echo("[4/4] chunked_corpus export finished, reading artifact back")
    fake_chunked = read_chunked_corpus_artifact(store, fake_chunked_artifact_id)

    normalized_summary = ArtifactSummary(
        artifact_id=normalized_artifact_id,
        complete=store.is_complete("normalized_dataset", normalized_artifact_id),
        manifest_path=str(
            local_root / "normalized_dataset" / normalized_artifact_id / "_MANIFEST.json"
        ),
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
        manifest_path=str(
            local_root / "chunked_corpus" / fake_chunked_artifact_id / "_MANIFEST.json"
        ),
        payload_path=str(local_root / "chunked_corpus" / fake_chunked_artifact_id),
        counts={"chunks": len(fake_chunked.chunks)},
    )

    result: dict[str, Any] = {
        "run_id": smoke_run_id,
        "repo_head": _repo_short_sha(REPO_ROOT),
        "task_name": TASK_NAME,
        "split": TASK_SPLIT,
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
            "This smoke uses real mteb.load_data() for IFIRNFCorpus.",
            "Set HF_ENDPOINT before running if you want to use a mirror.",
            "No embedding was run.",
            "No ES or Milvus index was created.",
            "No retrieval or metrics were run.",
        ],
    }
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
