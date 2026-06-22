"""Phase 6b: Medical term lexicon loaders.

Each source has its own loader class conforming to the BaseLoader interface.
All loaders return a pandas DataFrame conforming to the MedicalTermRecord schema.
"""
from src.term_inventory.loaders.icd10_backbone import BaseLoader, Icd10BackboneLoader
from src.term_inventory.loaders.rxnorm_loader import RxNormLoader

__all__ = [
    "BaseLoader",
    "Icd10BackboneLoader",
    "RxNormLoader",
]
