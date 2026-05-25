"""Tests for MTEB task loading helpers."""

from types import SimpleNamespace

import pytest

from eval_platform.mteb_adapter import MTEBAdapterError, extract_retrieval_data_from_mteb_task


class SplitAwareFakeTask:
    def __init__(self) -> None:
        self.load_data_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.corpus = {
            "test": {"doc-1": {"text": "Body"}},
        }
        self.queries = {
            "test": {"q-1": "query text"},
        }
        self.relevant_docs = {
            "test": {"q-1": {"doc-1": 1}},
        }

    def load_data(self, eval_splits: list[str] | None = None) -> None:
        self.load_data_calls.append(((), {"eval_splits": eval_splits}))


class FlatFakeTask:
    def __init__(self) -> None:
        self.load_data_called = False
        self.corpus = {"doc-1": {"text": "Body"}}
        self.queries = {"q-1": "query text"}
        self.qrels = {"q-1": {"doc-1": 1.0}}

    def load_data(self) -> None:
        self.load_data_called = True


class QrelsOnlyFakeTask:
    def __init__(self) -> None:
        self.corpus = {"doc-1": {"text": "Body"}}
        self.queries = {"q-1": "query text"}
        self.qrels = {"q-1": {"doc-1": 1}}


class FallbackLoadDataTask:
    def __init__(self) -> None:
        self.fallback_used = False
        self.corpus = {"doc-1": {"text": "Body"}}
        self.queries = {"q-1": "query text"}
        self.relevant_docs = {"q-1": {"doc-1": 1}}

    def load_data(self, eval_splits: list[str] | None = None) -> None:
        if eval_splits is not None:
            raise TypeError("unexpected keyword argument 'eval_splits'")
        self.fallback_used = True


class MissingFieldsTask:
    def load_data(self) -> None:
        return None


def test_extract_from_split_aware_task() -> None:
    task = SplitAwareFakeTask()

    corpus, queries, qrels = extract_retrieval_data_from_mteb_task(task, split="test")

    assert corpus == {"doc-1": {"text": "Body"}}
    assert queries == {"q-1": "query text"}
    assert qrels == {"q-1": {"doc-1": 1}}
    assert task.load_data_calls == [((), {"eval_splits": ["test"]})]


def test_extract_from_flat_task() -> None:
    task = FlatFakeTask()

    corpus, queries, qrels = extract_retrieval_data_from_mteb_task(task, split="test")

    assert corpus == {"doc-1": {"text": "Body"}}
    assert queries == {"q-1": "query text"}
    assert qrels == {"q-1": {"doc-1": 1.0}}
    assert task.load_data_called is True


def test_extract_uses_relevant_docs_when_present() -> None:
    task = SplitAwareFakeTask()

    _, _, qrels = extract_retrieval_data_from_mteb_task(task, split="test")

    assert qrels == {"q-1": {"doc-1": 1}}


def test_extract_uses_qrels_when_relevant_docs_missing() -> None:
    task = QrelsOnlyFakeTask()

    _, _, qrels = extract_retrieval_data_from_mteb_task(task, split="test")

    assert qrels == {"q-1": {"doc-1": 1}}


def test_extract_raises_when_required_fields_missing() -> None:
    task = MissingFieldsTask()

    with pytest.raises(MTEBAdapterError, match="missing corpus"):
        extract_retrieval_data_from_mteb_task(task, split="test")


def test_load_data_prefers_eval_splits_when_supported() -> None:
    task = SplitAwareFakeTask()

    extract_retrieval_data_from_mteb_task(task, split="test")

    assert task.load_data_calls[-1] == ((), {"eval_splits": ["test"]})


def test_load_data_falls_back_when_eval_splits_unsupported() -> None:
    task = FallbackLoadDataTask()

    corpus, queries, qrels = extract_retrieval_data_from_mteb_task(task, split="test")

    assert corpus == {"doc-1": {"text": "Body"}}
    assert queries == {"q-1": "query text"}
    assert qrels == {"q-1": {"doc-1": 1}}
    assert task.fallback_used is True


def test_extract_raises_when_queries_missing() -> None:
    task = SimpleNamespace(corpus={"doc-1": {"text": "Body"}}, relevant_docs={"q-1": {"doc-1": 1}})

    with pytest.raises(MTEBAdapterError, match="missing queries"):
        extract_retrieval_data_from_mteb_task(task, split="test")
