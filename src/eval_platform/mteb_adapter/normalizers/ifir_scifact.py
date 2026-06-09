"""Normalizer for the IFIRScifact MTEB retrieval task."""

from eval_platform.mteb_adapter.normalizers.ifir_base import IFIRMTEBNormalizer


class IFIRScifactNormalizer(IFIRMTEBNormalizer):
    task_name = "IFIRScifact"
