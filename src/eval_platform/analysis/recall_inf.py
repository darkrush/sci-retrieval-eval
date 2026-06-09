"""Recall@inf diagnostics over retrieval run traces."""

from __future__ import annotations

import json
from typing import Any

from eval_platform.artifacts import ArtifactStore
from eval_platform.artifacts.types import RETRIEVAL_RUN_ARTIFACT_TYPE
from eval_platform.datasets import read_normalized_dataset_artifact
from eval_platform.retrieval import RESULTS_DIR


class RecallInfAnalysisError(Exception):
    """Raised when recall@inf analysis cannot consume required artifacts."""


def compute_recall_inf_metrics(
    store: ArtifactStore,
    *,
    source_normalized_dataset_artifact_id: str,
    retrieval_run_artifact_id: str,
) -> dict[str, float]:
    """Compute recall@inf metrics by streaming retrieval shards to minimize memory."""
    dataset = read_normalized_dataset_artifact(store, source_normalized_dataset_artifact_id)

    qrels_by_query: dict[str, set[str]] = {}
    for qrel in dataset.qrels:
        if qrel.relevance <= 0:
            continue
        qrels_by_query.setdefault(qrel.query_id, set()).add(qrel.doc_id)
    if not qrels_by_query:
        return {}

    doc_id_sets = _stream_retrieval_doc_ids(store, retrieval_run_artifact_id)

    es_inf: list[float] = []
    milvus_inf: list[float] = []
    rrf_inf: list[float] = []
    rrf_es_inf: list[float] = []
    rrf_milvus_inf: list[float] = []
    for query_id, relevant_docs in sorted(qrels_by_query.items()):
        entry = doc_id_sets.get(query_id)
        if entry is None:
            es_inf.append(0.0)
            milvus_inf.append(0.0)
            rrf_inf.append(0.0)
            rrf_es_inf.append(0.0)
            rrf_milvus_inf.append(0.0)
            continue
        es_docs, milvus_docs, rrf_docs = entry
        es_inf.append(_recall_inf(es_docs, relevant_docs))
        milvus_inf.append(_recall_inf(milvus_docs, relevant_docs))
        rrf_inf.append(_recall_inf(rrf_docs, relevant_docs))
        rrf_es_inf.append(_recall_inf(rrf_docs & es_docs, relevant_docs))
        rrf_milvus_inf.append(_recall_inf(rrf_docs & milvus_docs, relevant_docs))
    return {
        "es_recall_at_inf": _mean(es_inf),
        "milvus_recall_at_inf": _mean(milvus_inf),
        "rrf_recall_at_inf": _mean(rrf_inf),
        "rrf_intersect_es_recall_at_inf": _mean(rrf_es_inf),
        "rrf_intersect_milvus_recall_at_inf": _mean(rrf_milvus_inf),
    }


def _stream_retrieval_doc_ids(
    store: ArtifactStore,
    retrieval_run_artifact_id: str,
) -> dict[str, tuple[set[str], set[str], set[str]]]:
    """Stream retrieval shards and extract only doc_id sets per query.

    Returns {query_id: (es_docs, milvus_docs, rrf_docs)}.
    Peak memory is proportional to one shard + the accumulated doc_id sets.
    """

    if not store.is_complete(RETRIEVAL_RUN_ARTIFACT_TYPE, retrieval_run_artifact_id):
        raise RecallInfAnalysisError(
            "retrieval_run artifact is not complete: "
            f"artifact_id={retrieval_run_artifact_id!r}"
        )

    manifest = store.read_manifest(RETRIEVAL_RUN_ARTIFACT_TYPE, retrieval_run_artifact_id)
    result: dict[str, tuple[set[str], set[str], set[str]]] = {}

    for artifact_file in manifest.files:
        if not artifact_file.path.startswith(f"{RESULTS_DIR}/"):
            continue
        payload = store.get_file(
            RETRIEVAL_RUN_ARTIFACT_TYPE,
            retrieval_run_artifact_id,
            artifact_file.path,
        ).decode("utf-8")
        for line in payload.splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            query_id = record.get("query_id", "")
            if not query_id:
                continue
            if record.get("error"):
                continue
            trace = record.get("trace")
            trace = trace if isinstance(trace, dict) else {}
            es_docs = _trace_doc_ids(trace, "es_hits")
            milvus_docs = _trace_doc_ids(trace, "milvus_hits")
            rrf_docs = _trace_doc_ids(trace, "paper_capped_hits")
            if not rrf_docs:
                rrf_docs = _trace_doc_ids(trace, "fused_hits")
            if not rrf_docs:
                rrf_docs = _record_doc_ids_from_raw(record.get("hits") or [])
            result[query_id] = (es_docs, milvus_docs, rrf_docs)
        del payload
    return result


def _record_doc_ids_from_raw(hits: list[Any]) -> set[str]:
    """Extract doc_ids from raw JSON hit dicts."""
    out: set[str] = set()
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        doc_id = _trace_hit_doc_id(hit)
        if doc_id:
            out.add(doc_id)
    return out


def _trace_doc_ids(trace: dict[str, Any], key: str) -> set[str]:
    out: set[str] = set()
    top_level = trace.get(key)
    if isinstance(top_level, list):
        for hit in top_level:
            if isinstance(hit, dict):
                doc_id = _trace_hit_doc_id(hit)
                if doc_id:
                    out.add(doc_id)
    per_query = trace.get("per_query")
    if isinstance(per_query, list):
        for item in per_query:
            if not isinstance(item, dict):
                continue
            query_hits = item.get(key)
            if not isinstance(query_hits, list):
                continue
            for hit in query_hits:
                if isinstance(hit, dict):
                    doc_id = _trace_hit_doc_id(hit)
                    if doc_id:
                        out.add(doc_id)
    return out


def _record_doc_ids(hits: list[Any]) -> set[str]:
    out: set[str] = set()
    for hit in hits:
        doc_id = _trace_hit_doc_id(
            {
                "doc_id": getattr(hit, "doc_id", ""),
                "chunk_id": getattr(hit, "chunk_id", ""),
                "metadata": getattr(hit, "metadata", {}) or {},
            }
        )
        if doc_id:
            out.add(doc_id)
    return out


def _trace_hit_doc_id(hit: dict[str, Any]) -> str:
    doc_id = str(hit.get("doc_id") or "").strip()
    if doc_id:
        return doc_id
    metadata = hit.get("metadata") or {}
    if isinstance(metadata, dict):
        paper_id = metadata.get("paper_id")
        if isinstance(paper_id, str) and paper_id.strip():
            return paper_id.strip()
    return str(hit.get("chunk_id") or "").strip()


def _recall_inf(doc_ids: set[str], relevant_docs: set[str]) -> float:
    if not relevant_docs:
        return 0.0
    return len(doc_ids & relevant_docs) / len(relevant_docs)


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
