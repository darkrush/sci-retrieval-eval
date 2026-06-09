"""Tests for dataset-specific MTEB normalizers."""

from types import SimpleNamespace

from eval_platform.mteb_adapter.normalizers.ifir_nfcorpus import IFIRNFCorpusNormalizer
from eval_platform.mteb_adapter.normalizers.ifir_scifact import IFIRScifactNormalizer
from eval_platform.mteb_adapter.normalizers.litsearch import LitSearchRetrievalNormalizer


def test_litsearch_normalizer_drops_empty_corpus_docs_and_orphan_queries() -> None:
    task = SimpleNamespace(
        corpus={
            "doc-1": {"title": "Title only", "text": ""},
            "doc-2": {"title": "", "text": ""},
            "doc-3": {"text": "Body"},
        },
        queries={
            "q-1": {"text": "query 1"},
            "q-2": {"text": "query 2"},
        },
        qrels={
            "q-1": {"doc-1": 1, "doc-2": 1},
            "q-2": {"doc-2": 1},
        },
    )

    dataset = LitSearchRetrievalNormalizer().normalize(task, split="test")

    assert [doc.doc_id for doc in dataset.corpus] == ["doc-1", "doc-3"]
    assert [query.query_id for query in dataset.queries] == ["q-1"]
    assert [(qrel.query_id, qrel.doc_id) for qrel in dataset.qrels] == [("q-1", "doc-1")]
    assert dataset.metadata["task_name"] == "LitSearchRetrieval"
    assert dataset.metadata["normalizer_name"] == "LitSearchRetrievalNormalizer"


def test_ifir_nfcorpus_normalizer_builds_mteb_effective_query() -> None:
    task = SimpleNamespace(
        corpus={"doc-1": {"text": "Body"}},
        queries={"q-1": {"text": "Q", "instruction": "Q I"}},
        relevant_docs={"q-1": {"doc-1": 1}},
    )

    dataset = IFIRNFCorpusNormalizer().normalize(task, split="test")

    assert dataset.queries[0].text == "Q Q I"
    assert dataset.queries[0].metadata == {
        "instruction": "Q I",
        "source_query_text": "Q",
        "effective_query_text": "Q Q I",
        "query_text_policy": "mteb_text_plus_instruction",
        "instruction_startswith_query_text": True,
    }
    assert dataset.metadata["query_text_policy"] == "mteb_text_plus_instruction"
    assert dataset.metadata["effective_query_text_field"] == "text"
    assert dataset.metadata["source_query_text_metadata_key"] == "source_query_text"


def test_ifir_scifact_normalizer_builds_mteb_effective_query() -> None:
    task = SimpleNamespace(
        corpus={"doc-1": {"text": "Body"}},
        queries={"q-1": {"text": "Q", "instruction": "Q I"}},
        relevant_docs={"q-1": {"doc-1": 1}},
    )

    dataset = IFIRScifactNormalizer().normalize(task, split="test")

    assert dataset.queries[0].text == "Q Q I"
    assert dataset.queries[0].metadata["query_text_policy"] == "mteb_text_plus_instruction"
    assert dataset.metadata["task_name"] == "IFIRScifact"


def test_ifir_normalizer_records_instruction_without_query_prefix() -> None:
    task = SimpleNamespace(
        corpus={"doc-1": {"text": "Body"}},
        queries={"q-1": {"text": "Q", "instruction": "I"}},
        relevant_docs={"q-1": {"doc-1": 1}},
    )

    dataset = IFIRNFCorpusNormalizer().normalize(task, split="test")

    assert dataset.queries[0].text == "Q I"
    assert dataset.queries[0].metadata["instruction_startswith_query_text"] is False


def test_ifir_normalizer_does_not_recombine_existing_effective_query() -> None:
    task = SimpleNamespace(
        corpus={"doc-1": {"text": "Body"}},
        queries={
            "q-1": {
                "text": "Q Q I",
                "instruction": "Q I",
                "source_query_text": "Q",
                "query_text_policy": "mteb_loader_effective_text",
            }
        },
        relevant_docs={"q-1": {"doc-1": 1}},
    )

    dataset = IFIRNFCorpusNormalizer().normalize(task, split="test")

    assert dataset.queries[0].text == "Q Q I"
    assert dataset.queries[0].metadata == {
        "instruction": "Q I",
        "source_query_text": "Q",
        "query_text_policy": "mteb_loader_effective_text",
    }


def test_ifir_normalizer_uses_existing_effective_query_text() -> None:
    task = SimpleNamespace(
        corpus={"doc-1": {"text": "Body"}},
        queries={
            "q-1": {
                "text": "Q",
                "instruction": "Q I",
                "effective_query_text": "Q Q I",
                "source_query_text": "Q",
            }
        },
        relevant_docs={"q-1": {"doc-1": 1}},
    )

    dataset = IFIRNFCorpusNormalizer().normalize(task, split="test")

    assert dataset.queries[0].text == "Q Q I"
    assert dataset.queries[0].metadata == {
        "instruction": "Q I",
        "effective_query_text": "Q Q I",
        "source_query_text": "Q",
        "query_text_policy": "mteb_loader_effective_text",
    }
