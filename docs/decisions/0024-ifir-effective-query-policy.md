# 0024. IFIR Effective Query Policy

- Status: Accepted
- Date: 2026-06-09

## Context

IFIR is instruction-following retrieval, not a plain SciFact or NFCorpus query set. The same
source query can have instruction-specific query variants, and qrels are defined for those variants.
Using only the original query silently drops the instruction signal and changes the evaluation
target.

Two source layouts need different handling:

- MTEB `if-ir/*` tasks expose `queries.text` and `instructions.instruction`. MTEB constructs the
  final query as `queries.text + " " + instructions.instruction`.
- The original IFIR repository has raw instructions that do not include the source query, while some
  generated `*-query.jsonl` files already contain one-pass instruction queries.

The pinned MTEB IFIR revisions currently have `instructions.instruction` values that already start
with the query text. Strict MTEB reproduction therefore produces a repeated query prefix:

```text
source query + " " + source query + " " + instruction body
```

This is intentionally preserved. Automatically deduplicating the repeated query would diverge from
the MTEB loader behavior.

## Decision

Raw-to-normalized IFIR datasets use an explicit `query_text_policy`.

`IFIRNFCorpus` and `IFIRScifact` default to:

```text
mteb_text_plus_instruction
```

This policy always computes:

```text
effective_query_text = query_text + " " + instruction
```

even when `instruction.startswith(query_text)` is true.

The platform also supports:

```text
ifir_original_query_plus_instruction_once
```

This policy uses the same one-pass concatenation but rejects input where the instruction already
starts with the query text, because that indicates an already-combined query layout and would risk a
double append.

For IFIR raw normalization:

- `QueryRecord.text` is the effective query used by downstream embedding and retrieval.
- Query metadata stores `source_query_text`, `instruction`, `effective_query_text`,
  `query_text_policy`, and `instruction_startswith_query_text`.
- Missing instructions are errors. IFIR must not silently fall back to plain query text.
- Manifest metadata records `has_instructions`, `query_text_policy`, `effective_query_text_field`,
  `source_query_text_metadata_key`, and `instruction_startswith_query_text_count`.

For generic MTEB adapter conversion, the adapter trusts the MTEB loader output. If MTEB already
returns an effective `text`, the platform does not combine it with `instruction` again.

## Consequences

Newly generated IFIR normalized datasets will have different query text from older artifacts that
only used the source query. Downstream chunk-independent assets that depend on normalized query text,
such as retrieval runs, metrics runs, and their fingerprints, should change. This is expected and
fixes the evaluation target.

Plain `NFCorpus` and `SciFact` normalizers do not set an IFIR query policy and do not rewrite query
text.
