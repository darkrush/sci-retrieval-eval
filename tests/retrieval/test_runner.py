"""Tests for retrieval run orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from eval_platform.artifacts import LocalArtifactStore
from eval_platform.datasets import (
    CorpusRecord,
    NormalizedDataset,
    QrelRecord,
    QueryRecord,
    write_normalized_dataset_artifact,
)
from eval_platform.retrieval import (
    RETRIEVAL_RUN_ARTIFACT_TYPE,
    RetrievalHit,
    RetrievalRunConfig,
    RetrievalRunError,
    read_retrieval_run_artifact,
    run_retrieval,
)


@pytest.fixture
def store(tmp_path: Path) -> LocalArtifactStore:
    artifact_store = LocalArtifactStore(tmp_path)
    write_normalized_dataset_artifact(
        artifact_store,
        "normalized-1",
        NormalizedDataset(
            corpus=[CorpusRecord(doc_id="doc-1", text="doc")],
            queries=[
                QueryRecord(query_id="q-1", text="alpha query"),
                QueryRecord(query_id="q-2", text="error query"),
            ],
            qrels=[QrelRecord(query_id="q-1", doc_id="doc-1")],
        ),
    )
    return artifact_store


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[float(index), float(len(text))] for index, text in enumerate(texts, start=1)]


class FakeElasticsearchClient:
    def __init__(self) -> None:
        self.search_calls: list[tuple[str, str, int]] = []
        self.enrich_calls: list[list[str]] = []

    def search_bm25(self, index_name: str, query: str, top_k: int) -> list[RetrievalHit]:
        self.search_calls.append((index_name, query, top_k))
        if query == "error query":
            raise RuntimeError("boom")
        return [
            RetrievalHit(
                chunk_id=f"es-{query}-{index}",
                doc_id=f"doc-es-{index}",
                title=f"title {index}",
                text=f"es text {query} {index}",
                score=10.0 - index,
                recall_source="es",
            )
            for index in range(1, top_k + 1)
        ]

    def enrich_by_chunk_ids(
        self,
        index_name: str,
        hits: Sequence[RetrievalHit],
    ) -> list[RetrievalHit]:
        self.enrich_calls.append([hit.chunk_id for hit in hits])
        return [
            hit.model_copy(
                update={
                    "doc_id": hit.doc_id or f"doc-{hit.chunk_id}",
                    "title": hit.title or f"title {hit.chunk_id}",
                    "text": hit.text or f"text {hit.chunk_id}",
                }
            )
            for hit in hits
        ]


class FakeMilvusClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[float], int]] = []

    def search(
        self,
        collection_name: str,
        vector: Sequence[float],
        top_k: int,
    ) -> list[RetrievalHit]:
        self.calls.append((collection_name, list(vector), top_k))
        return [
            RetrievalHit(
                chunk_id=f"mv-{index}",
                doc_id=f"doc-mv-{index}",
                score=1.0 / index,
                recall_source="milvus",
            )
            for index in range(1, top_k + 1)
        ]


class FakeRewriteClient:
    def __init__(self, rewrites: list[str]) -> None:
        self.rewrites = rewrites
        self.calls: list[tuple[str, int]] = []

    def rewrite(self, query: str, max_queries: int) -> list[str]:
        self.calls.append((query, max_queries))
        return self.rewrites


class FakeRerankClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str], int]] = []

    def rerank(
        self,
        query: str,
        hits: Sequence[RetrievalHit],
        top_n: int,
    ) -> list[RetrievalHit]:
        self.calls.append((query, [hit.chunk_id for hit in hits], top_n))
        return [
            hit.model_copy(update={"score": 100.0 - index})
            for index, hit in enumerate(reversed(hits[:top_n]), start=1)
        ]


def _config(**overrides: Any) -> RetrievalRunConfig:
    payload: dict[str, Any] = {
        "source_normalized_dataset_artifact_id": "normalized-1",
        "output_artifact_id": "retrieval-1",
        "retrieval_mode": "hybrid",
        "top_k": 2,
        "query_limit": 1,
        "elasticsearch_index_artifact_id": "es-artifact",
        "milvus_collection_artifact_id": "milvus-artifact",
        "index_name": "chunks-index",
        "collection_name": "chunks-collection",
        "hybrid_per_source_topk": 3,
        "rrf_path_topk": 2,
    }
    payload.update(overrides)
    return RetrievalRunConfig(**payload)


def test_run_retrieval_es_mode_uses_only_elasticsearch(store: LocalArtifactStore) -> None:
    es = FakeElasticsearchClient()
    embedding = FakeEmbeddingClient()
    milvus = FakeMilvusClient()

    manifest = run_retrieval(
        store,
        store,
        _config(retrieval_mode="es", milvus_collection_artifact_id=None),
        es_client=es,
        embedding_client=embedding,
        milvus_client=milvus,
    )
    records = read_retrieval_run_artifact(store, "retrieval-1")

    assert len(es.search_calls) == 1
    assert embedding.calls == []
    assert milvus.calls == []
    assert [hit.rank for hit in records[0].hits] == [1, 2]
    assert manifest.metadata["retrieval_mode"] == "es"


def test_run_retrieval_milvus_mode_embeds_searches_and_enriches(
    store: LocalArtifactStore,
) -> None:
    es = FakeElasticsearchClient()
    embedding = FakeEmbeddingClient()
    milvus = FakeMilvusClient()

    run_retrieval(
        store,
        store,
        _config(retrieval_mode="milvus"),
        es_client=es,
        embedding_client=embedding,
        milvus_client=milvus,
    )
    records = read_retrieval_run_artifact(store, "retrieval-1")

    assert embedding.calls == [["alpha query"]]
    assert milvus.calls[0][0] == "chunks-collection"
    assert es.search_calls == []
    assert es.enrich_calls == [["mv-1", "mv-2"]]
    assert records[0].hits[0].text == "text mv-1"


def test_run_retrieval_hybrid_runs_rrf_and_enriches(store: LocalArtifactStore) -> None:
    es = FakeElasticsearchClient()
    embedding = FakeEmbeddingClient()
    milvus = FakeMilvusClient()

    manifest = run_retrieval(
        store,
        store,
        _config(retrieval_mode="hybrid"),
        es_client=es,
        embedding_client=embedding,
        milvus_client=milvus,
    )
    records = read_retrieval_run_artifact(store, "retrieval-1")

    assert embedding.calls == [["alpha query"]]
    assert milvus.calls[0][2] == 3
    assert es.search_calls[0] == ("chunks-index", "alpha query", 3)
    assert records[0].hits[0].rank == 1
    assert [(dep.artifact_type, dep.artifact_id) for dep in manifest.dependencies] == [
        ("normalized_dataset", "normalized-1"),
        ("elasticsearch_index", "es-artifact"),
        ("milvus_collection", "milvus-artifact"),
    ]
    assert manifest.metadata["query_count"] == 1
    assert manifest.metadata["result_record_count"] == 1


def test_run_retrieval_rewrite_dedupes_and_batches_embedding(
    store: LocalArtifactStore,
) -> None:
    es = FakeElasticsearchClient()
    embedding = FakeEmbeddingClient()
    milvus = FakeMilvusClient()
    rewrite = FakeRewriteClient([" ", "ALPHA QUERY", "beta query", "beta query", "gamma query"])

    run_retrieval(
        store,
        store,
        _config(
            retrieval_mode="milvus",
            rewrite_enabled=True,
            sub_queries=2,
            include_trace=True,
        ),
        es_client=es,
        embedding_client=embedding,
        milvus_client=milvus,
        rewrite_client=rewrite,
    )
    records = read_retrieval_run_artifact(store, "retrieval-1")

    assert embedding.calls == [["alpha query", "beta query", "gamma query"]]
    assert records[0].trace is not None
    assert records[0].trace["rewrite_queries"] == ["alpha query", "beta query", "gamma query"]


def test_run_retrieval_rerank_caps_head_and_preserves_tail(
    store: LocalArtifactStore,
) -> None:
    es = FakeElasticsearchClient()
    rerank = FakeRerankClient()

    run_retrieval(
        store,
        store,
        _config(
            retrieval_mode="es",
            milvus_collection_artifact_id=None,
            top_k=3,
            rerank_enabled=True,
            rerank_candidate_cap=2,
            rerank_cross_path_topk=2,
            include_trace=True,
        ),
        es_client=es,
        rerank_client=rerank,
    )
    records = read_retrieval_run_artifact(store, "retrieval-1")

    assert rerank.calls == [("alpha query", ["es-alpha query-1", "es-alpha query-2"], 2)]
    assert [hit.chunk_id for hit in records[0].hits] == [
        "es-alpha query-2",
        "es-alpha query-1",
        "es-alpha query-3",
    ]
    assert records[0].trace is not None
    assert [hit["chunk_id"] for hit in records[0].trace["rerank_input"]] == [
        "es-alpha query-1",
        "es-alpha query-2",
    ]


def test_run_retrieval_records_query_error_and_continues(store: LocalArtifactStore) -> None:
    es = FakeElasticsearchClient()

    manifest = run_retrieval(
        store,
        store,
        _config(
            retrieval_mode="es",
            milvus_collection_artifact_id=None,
            query_limit=None,
        ),
        es_client=es,
    )
    records = read_retrieval_run_artifact(store, "retrieval-1")

    assert len(records) == 2
    assert records[0].error is None
    assert records[1].error == "boom"
    assert manifest.metadata["failed_query_count"] == 1
    assert store.is_complete(RETRIEVAL_RUN_ARTIFACT_TYPE, "retrieval-1") is True


def test_run_retrieval_requires_missing_clients_before_writing(
    store: LocalArtifactStore,
) -> None:
    with pytest.raises(RetrievalRunError, match="embedding_client"):
        run_retrieval(
            store,
            store,
            _config(retrieval_mode="milvus"),
            es_client=FakeElasticsearchClient(),
            milvus_client=FakeMilvusClient(),
        )

    assert store.is_complete(RETRIEVAL_RUN_ARTIFACT_TYPE, "retrieval-1") is False
