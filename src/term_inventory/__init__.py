"""Phase 6b: Medical Term Inventory Extended.

Builds a comprehensive multi-source medical term inventory from ICD-10 disease
backbone plus supplementary lexicons (drug, lab test, procedure, abbreviation,
hormone, biomarker, device, unit, dosage).

Usage:
    python -m src.term_inventory.cli build-inventory --mock
    python -m src.term_inventory.cli build-inventory --full
"""
from src.term_inventory.schemas import (
    EntityType,
    InventoryClassificationBatchResponse,
    InventoryClassificationItem,
    InventoryConfig,
    MedicalTermRecord,
    Phase2ToFr2EntityTypeMap,
    ReviewStatus,
    TermSource,
)
from src.term_inventory.loaders import BaseLoader

__all__ = [
    "EntityType",
    "ReviewStatus",
    "TermSource",
    "MedicalTermRecord",
    "InventoryConfig",
    "Phase2ToFr2EntityTypeMap",
    "InventoryClassificationItem",
    "InventoryClassificationBatchResponse",
    "BaseLoader",
]
