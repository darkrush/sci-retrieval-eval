"""Chunked corpus record schemas."""

from typing import Any

from pydantic import BaseModel, Field, ValidationInfo, field_validator


def _non_empty_string(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value


class ChunkerProvenance(BaseModel):
    """Provenance metadata for the external chunker implementation."""

    name: str
    repo_url: str | None = None
    repo_path: str | None = None
    commit_sha: str
    branch: str | None = None
    is_dirty: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", "commit_sha")
    @classmethod
    def validate_non_empty(cls, value: str, info: ValidationInfo) -> str:
        return _non_empty_string(value, info.field_name or "field")


class ChunkRecord(BaseModel):
    """A single chunk derived from a source document."""

    chunk_id: str
    doc_id: str
    text: str
    title: str | None = None
    chunk_index: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("chunk_id", "doc_id", "text")
    @classmethod
    def validate_non_empty(cls, value: str, info: ValidationInfo) -> str:
        return _non_empty_string(value, info.field_name or "field")


class ChunkedCorpus(BaseModel):
    """In-memory container for a chunked corpus."""

    chunks: list[ChunkRecord]
    metadata: dict[str, Any] = Field(default_factory=dict)
