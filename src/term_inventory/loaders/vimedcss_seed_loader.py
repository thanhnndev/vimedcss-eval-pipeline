"""ViMedCSS seed term loader for Phase 6b.

Loads terms from the Phase 1 CS term inventory CSV
(outputs/term_coverage/cs_terms_inventory.csv). These are ViMedCSS-sourced
English/Vietnamese code-switching medical terms extracted from the dataset.

The seed loader provides the bridge between Phase 1 (ViMedCSS CS terms) and
the medical term inventory. These terms get entity_type=unknown and
medical_domain=None here — classification happens in Plan 04 via LLM.

Source: outputs/term_coverage/cs_terms_inventory.csv (Phase 1 output).
"""
import os
from datetime import datetime, timezone

import pandas as pd

from src.term_inventory.loaders.icd10_backbone import BaseLoader
from src.term_inventory.schemas import (
    EntityType,
    InventoryConfig,
    ReviewStatus,
    TermSource,
)
from src.shared.logging import setup_logger

logger = setup_logger("vimedcss_seed_loader")

# Path to Phase 1 output file
DEFAULT_SEED_PATH = "outputs/term_coverage/cs_terms_inventory.csv"


class VimedcssSeedLoader(BaseLoader):
    """Load ViMedCSS-sourced terms from the Phase 1 CS term inventory.

    Reads the Phase 1 output CSV and maps each row to MedicalTermRecord schema.
    entity_type is set to `unknown` — classification by entity type and
    medical_domain happens in Plan 04 via LLM.
    """

    def __init__(self, config: InventoryConfig):
        self.config = config
        # Allow config override, default to Phase 1 output path
        self.seed_path = os.environ.get(
            "VIMEDCSS_SEED_PATH",
            DEFAULT_SEED_PATH,
        )

    def load(self) -> pd.DataFrame:
        """Load ViMedCSS seed terms from Phase 1 inventory CSV.

        Returns:
            DataFrame with MedicalTermRecord columns, one row per CS term.
            Raises FileNotFoundError if Phase 1 output is missing.

        Raises:
            FileNotFoundError: if the seed CSV does not exist.
        """
        if not os.path.exists(self.seed_path):
            raise FileNotFoundError(
                f"Phase 1 output not found at: {self.seed_path}\n"
                "Run Phase 1 (CS Term Extraction) first to generate it, "
                "or set VIMEDCSS_SEED_PATH to the correct path."
            )

        logger.info(f"Loading ViMedCSS seed terms from {self.seed_path}")
        df = pd.read_csv(self.seed_path, dtype=str).fillna("")
        initial_rows = len(df)

        if df.empty:
            logger.warning("ViMedCSS seed CSV is empty.")
            return pd.DataFrame(columns=self.REQUIRED_COLS)

        rows: list[dict] = []
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        term_counter = 1

        for _, row in df.iterrows():
            # Use canonical_term if available, otherwise fall back to normalized_term
            canonical = row.get("canonical_term", "").strip()
            normalized = row.get("normalized_term", "").strip()
            term_original = canonical if canonical else normalized
            if not term_original:
                continue

            # Map Phase 2 entity_category to FR2-04 EntityType via Phase2ToFr2EntityTypeMap
            phase2_category = row.get("entity_category", "unknown").strip()
            from src.term_inventory.schemas import Phase2ToFr2EntityTypeMap
            entity_type = Phase2ToFr2EntityTypeMap.get(
                phase2_category, EntityType.UNKNOWN
            )

            # Capture Phase 1 specialty and domain as hints for downstream LLM classification
            specialty = row.get("specialty", "").strip() or None
            medical_domain = row.get("medical_domain", "").strip() or None

            rows.append({
                "term_id": f"term_{term_counter:06d}",
                "term_original": term_original,
                "term_normalized": term_original.lower().strip(),
                "entity_type": entity_type.value if hasattr(entity_type, "value") else entity_type,
                "medical_domain": medical_domain,
                "source_name": TermSource.VIMEDCSS_SEED.value,
                "source_url": None,
                "source_license": None,
                "icd10_code": None,
                "rxnorm_rxcui": None,
                "is_code_switch_candidate": True,
                "review_status": ReviewStatus.NEEDS_REVIEW.value,
                "llm_generated_candidate": False,
                "fetched_at": now,
                # Extra columns from Phase 1
                "phase1_specialty": specialty,
                "phase1_entity_category": phase2_category or None,
                "phase1_occurrence_count": row.get("occurrence_count", "").strip() or None,
                "phase1_frequency_bucket": row.get("frequency_bucket", "").strip() or None,
            })
            term_counter += 1

        result = pd.DataFrame(rows)
        self._validate(result)

        dropped = initial_rows - len(result)
        if dropped > 0:
            logger.debug(f"Dropped {dropped} rows with empty term values.")

        logger.info(
            f"VimedcssSeedLoader loaded {len(result)} ViMedCSS seed terms "
            f"from Phase 1 output ({initial_rows} raw rows)."
        )
        return result
