"""Shared IFIR MTEB normalizer behavior."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from eval_platform.datasets.schema import NormalizedDataset
from eval_platform.mteb_adapter.base import GenericRetrievalTaskNormalizer
from eval_platform.mteb_adapter.convert import convert_retrieval_data_to_normalized_dataset

MTEB_TEXT_PLUS_INSTRUCTION_POLICY = "mteb_text_plus_instruction"
MTEB_LOADER_EFFECTIVE_TEXT_POLICY = "mteb_loader_effective_text"


class IFIRMTEBNormalizer(GenericRetrievalTaskNormalizer):
    """Normalizer for MTEB IFIR tasks with explicit effective query text."""

    def normalize(self, task: Any, split: str = "test") -> NormalizedDataset:
        corpus, queries, qrels = self.extract_raw(task, split)
        converted_queries = _convert_ifir_queries(queries)
        return convert_retrieval_data_to_normalized_dataset(
            corpus=corpus,
            queries=converted_queries,
            qrels=qrels,
            metadata={
                "source": "mteb",
                "task_name": self.task_name,
                "split": split,
                "normalizer_name": self.normalizer_name,
                "query_text_policy": MTEB_TEXT_PLUS_INSTRUCTION_POLICY,
                "effective_query_text_field": "text",
                "source_query_text_metadata_key": "source_query_text",
            },
        )


def _convert_ifir_queries(queries: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(query_id): _convert_ifir_query_payload(payload)
        for query_id, payload in queries.items()
    }


def _convert_ifir_query_payload(payload: Any) -> Any:
    if not isinstance(payload, Mapping):
        return payload

    payload_dict = dict(payload)
    existing_effective_text = payload_dict.get("effective_query_text")
    if isinstance(existing_effective_text, str) and existing_effective_text.strip():
        payload_dict["text"] = existing_effective_text
        payload_dict.setdefault("query_text_policy", MTEB_LOADER_EFFECTIVE_TEXT_POLICY)
        return payload_dict

    if payload_dict.get("query_text_policy") == MTEB_LOADER_EFFECTIVE_TEXT_POLICY:
        return payload_dict

    text = payload_dict.get("text")
    instruction = payload_dict.get("instruction")
    if not (isinstance(text, str) and text.strip()):
        return payload_dict
    if not (isinstance(instruction, str) and instruction.strip()):
        return payload_dict

    effective_query_text = f"{text} {instruction}"
    payload_dict["text"] = effective_query_text
    payload_dict["source_query_text"] = text
    payload_dict["instruction"] = instruction
    payload_dict["effective_query_text"] = effective_query_text
    payload_dict["query_text_policy"] = MTEB_TEXT_PLUS_INSTRUCTION_POLICY
    payload_dict["instruction_startswith_query_text"] = instruction.startswith(text)
    return payload_dict
