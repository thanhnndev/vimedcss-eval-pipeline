"""Phase 6b: Medical term lexicon loaders.

Each source has its own loader class conforming to the BaseLoader interface.
All loaders return a pandas DataFrame conforming to the MedicalTermRecord schema.

Imported lazily to allow incremental implementation (e.g. stub loader modules).
Use `from src.term_inventory.loaders.icd10_backbone import Icd10BackboneLoader`
for direct imports when only a subset of loaders is needed.
"""
from src.term_inventory.loaders.icd10_backbone import BaseLoader, Icd10BackboneLoader

__all__ = [
    "BaseLoader",
    "Icd10BackboneLoader",
]
