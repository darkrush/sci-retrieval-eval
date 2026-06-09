"""Normalizer for the IFIRNFCorpus MTEB retrieval task."""

from eval_platform.mteb_adapter.normalizers.ifir_base import IFIRMTEBNormalizer


class IFIRNFCorpusNormalizer(IFIRMTEBNormalizer):
    task_name = "IFIRNFCorpus"
