# Five Dataset Corpus Assets

This note documents the safe preparation path for the five target retrieval datasets:

- IFIRNFCorpus
- NFCorpus
- IFIRScifact
- SciFact
- LitSearchRetrieval

The goal is to make every dataset available as the same artifact chain:

```text
raw_dataset
normalized_dataset
chunked_corpus
embeddings
elasticsearch_index
milvus_collection
```

## Raw Layout

The immutable raw prefixes are expected under:

```text
s3://<bucket>/sciverse_benchmark/raw/<dataset_slug>/
```

Dataset slugs:

```text
IFIRNFCorpus       -> ifir_nfcorpus
NFCorpus           -> nfcorpus
IFIRScifact        -> ifir_scifact
SciFact            -> scifact
LitSearchRetrieval -> litsearch
```

Expected raw files:

- IFIR datasets: `corpus.jsonl`, `queries.jsonl`, `instructions.jsonl`, `qrels/test.tsv`
- NFCorpus/SciFact: `corpus.jsonl`, `queries.jsonl`, `qrels/test.tsv`
- LitSearchRetrieval: `corpus/test-00000-of-00001.parquet`, `queries/test-00000-of-00001.parquet`, `qrels/test-00000-of-00001.parquet`

These layouts match the existing raw normalizer registry in `eval_platform.datasets.raw_normalize`.

## Artifact Naming

For a `run_id`, artifact ids are:

```text
<dataset_slug>_<run_id>_raw
<dataset_slug>_<run_id>_normalized
<dataset_slug>_<run_id>_chunks
<dataset_slug>_<run_id>_embeddings
<dataset_slug>_<run_id>_es_index
<dataset_slug>_<run_id>_milvus_collection
```

Index names:

```text
<dataset_slug>_<run_id>_es
<dataset_slug>_<run_id>_milvus
```

## Inventory

Inventory is read-only:

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY \
python scripts/inventory_real_corpus_assets.py \
  --config /home/qiujiuantao/codex_project/sci-base/sciverse_benchmark/config.yaml \
  --s3-prefix test_sciverse_benchmark \
  --raw-prefix sciverse_benchmark/raw
```

The output reports:

- raw prefix existence
- existing artifact ids by type
- `_MANIFEST.json` and `_SUCCESS` status
- selected manifest metadata such as counts, source artifact ids, index/collection names, and failed/verified counts
- missing stages per dataset

The config dump is redacted before printing.

## Dry-Run Build Plan

Build planning is dry-run by default:

```bash
python scripts/build_real_corpus_assets.py \
  --config /home/qiujiuantao/codex_project/sci-base/sciverse_benchmark/config.yaml \
  --dataset IFIRNFCorpus \
  --run-id five_ds_20260527_001 \
  --s3-prefix test_sciverse_benchmark \
  --dry-run
```

Use `--dataset all` to plan all five datasets.

Each dataset plan includes three artifact-id views:

- `generated_artifact_ids`: ids that would be created for the current `run_id`.
- `resolved_artifact_ids`: ids that downstream stages should actually consume.
- `artifact_ids`: compatibility alias for `generated_artifact_ids`.

Without `--reuse-existing`, `generated_artifact_ids` and `resolved_artifact_ids` are the
same. With `--reuse-existing`, any complete existing artifact selected from inventory is
recorded in `resolved_artifact_ids`; downstream dependencies use those resolved ids.
For example, if existing chunks and embeddings are reused, the Elasticsearch step reads the
reused `chunked_corpus` artifact and the Milvus step reads the reused `chunked_corpus` and
`embeddings` artifacts.

The current script intentionally refuses `--execute`. Real execution still needs explicit runtime clients for chunking, embedding, Elasticsearch ingest, and Milvus ingest. The generated plan is meant to drive the existing `corpus_build` runner safely without inventing another execution path.

## Safety Rules

- Do not commit real config files or generated inventory reports.
- Do not write outside the test S3 artifact prefix unless explicitly instructed.
- Do not overwrite existing artifact ids; use a new run id.
- Do not reuse existing artifacts unless `--reuse-existing` is explicitly supplied.
- Do not print API keys, passwords, S3 access keys, or Authorization headers.
