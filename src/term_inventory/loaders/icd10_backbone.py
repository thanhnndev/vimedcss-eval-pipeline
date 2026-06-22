"""ICD-10 backbone loader for Phase 6b.

Loads disease terms from the Phase 6a bilingual ICD-10 CSV output.
Filters to level=type rows (specific disease codes, not section/chapter headers),
maps them to MedicalTermRecord schema, and marks all as `verified` since ICD-10
is an authoritative government-maintained source.
"""
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import pandas as pd

from src.shared.logging import setup_logger
from src.term_inventory.schemas import (
    EntityType,
    InventoryConfig,
    MedicalTermRecord,
    ReviewStatus,
    TermSource,
)

logger = setup_logger("icd10_backbone_loader")


class BaseLoader(ABC):
    """Abstract base for all term lexicon loaders.

    All loaders return a DataFrame conforming to the MedicalTermRecord schema
    (flattened to columns). Subclasses must implement the `load()` method.
    """

    REQUIRED_COLS = [
        "term_original",
        "term_normalized",
        "entity_type",
        "source_name",
        "source_url",
        "review_status",
    ]

    @abstractmethod
    def load(self) -> pd.DataFrame:
        """Load terms from this source.

        Returns:
            DataFrame with REQUIRED_COLS plus optional extra columns.
            Extra columns (e.g. label_vi, chapter_label_en) are preserved for
            downstream normalization and reporting.
        """
        pass

    def _validate(self, df: pd.DataFrame) -> None:
        """Validate required columns are present.

        Raises:
            ValueError: if any required columns are missing.
        """
        missing = [c for c in self.REQUIRED_COLS if c not in df.columns]
        if missing:
            raise ValueError(
                f"{self.__class__.__name__} output is missing required columns: {missing}. "
                f"Found columns: {list(df.columns)}"
            )


class Icd10BackboneLoader(BaseLoader):
    """Load disease terms from the Phase 6a ICD-10 bilingual CSV.

    The source file (`data/icd10/icd10_dual_language.csv`) contains:
        code, level, label_en, label_vi, chapter_code, chapter_label_en,
        chapter_label_vi, parent_code, source, source_url, fetched_at

    Only `level == "type"` rows are disease codes (not section/chapter headers).
    All loaded terms are marked `verified` — ICD-10 is authoritative.
    """

    def __init__(self, config: InventoryConfig):
        self.config = config
        self.backbone_path = config.icd10_backbone_path

    def load(self) -> pd.DataFrame:
        if not os.path.exists(self.backbone_path):
            raise FileNotFoundError(
                f"ICD-10 backbone file not found: {self.backbone_path}\n"
                "Run Phase 6a (icd-10-dual-language-ingestion) to generate it, "
                "or use --mock to skip this source."
            )

        logger.info(f"Loading ICD-10 backbone from {self.backbone_path}")
        df = pd.read_csv(self.backbone_path, dtype=str).fillna("")

        # Filter to disease-level rows only (not section/chapter headers)
        initial_rows = len(df)
        df = df[df["level"] == "type"].copy()
        dropped = initial_rows - len(df)
        if dropped > 0:
            logger.debug(f"Dropped {dropped} non-disease rows (level != 'type').")

        if df.empty:
            logger.warning(
                "ICD-10 backbone has no 'type' level rows. "
                "Check that the Phase 6a output file is correct."
            )
            return pd.DataFrame()

        # Map to MedicalTermRecord schema
        rows = []
        term_counter = 1
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        for _, row in df.iterrows():
            label_en = row["label_en"].strip()
            term_normalized = label_en.lower().strip()

            rows.append(
                {
                    "term_id": f"term_{term_counter:06d}",
                    "term_original": label_en,
                    "term_normalized": term_normalized,
                    "entity_type": EntityType.DISEASE.value,
                    "medical_domain": None,
                    "source_name": TermSource.ICD10.value,
                    "source_url": row["source_url"] or None,
                    "source_license": None,
                    "icd10_code": row["code"].strip() or None,
                    "rxnorm_rxcui": None,
                    "is_code_switch_candidate": True,
                    "review_status": ReviewStatus.VERIFIED.value,
                    "llm_generated_candidate": False,
                    "fetched_at": row["fetched_at"] or now,
                    # Extra columns for downstream use
                    "label_vi": row["label_vi"].strip(),
                    "chapter_label_en": row["chapter_label_en"].strip(),
                }
            )
            term_counter += 1

        result = pd.DataFrame(rows)
        self._validate(result)

        logger.info(
            f"Loaded {len(result)} disease terms from ICD-10 backbone. "
            f"Sample: {result.iloc[0]['term_original']!r} ({result.iloc[0]['icd10_code']})"
        )
        return result
