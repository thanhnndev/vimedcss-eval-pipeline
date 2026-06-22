"""Abbreviation and ViMedCSS seed loaders for Phase 6b.

- AbbreviationLoader: Maps medical abbreviations to their expansions from a config list.
  Creates two rows per abbreviation: one for the abbreviation itself and one for the
  expansion (if available). Source: configs/term_inventory.yaml#abbreviation_list.

- VimedcssSeedLoader: Loads terms from the Phase 1 CS term inventory CSV
  (outputs/term_coverage/cs_terms_inventory.csv). These are ViMedCSS-sourced terms
  that will get entity_type and medical_domain classified in Plan 04 via LLM.
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

logger = setup_logger("abbreviation_loader")

# Medical abbreviation → expansion mapping
# Covers common EN/VI CS medical abbreviations found in clinical documentation
ABBREVIATION_EXPANSION_MAP = {
    "ECG": "electrocardiogram",
    "EEG": "electroencephalogram",
    "MRI": "magnetic resonance imaging",
    "CT": "computed tomography",
    "CBC": "complete blood count",
    "ICU": "intensive care unit",
    "ER": "emergency room",
    "IV": "intravenous",
    "IM": "intramuscular",
    "BP": "blood pressure",
    "HR": "heart rate",
    "WBC": "white blood cell",
    "RBC": "red blood cell",
    "CRP": "c-reactive protein",
    "HbA1c": "hemoglobin A1c",
    "eGFR": "estimated glomerular filtration rate",
    "PSA": "prostate specific antigen",
    "HDL": "high density lipoprotein",
    "LDL": "low density lipoprotein",
    "COPD": "chronic obstructive pulmonary disease",
    "UTI": "urinary tract infection",
    "GERD": "gastroesophageal reflux disease",
    "HIV": "human immunodeficiency virus",
    "AIDS": "acquired immunodeficiency syndrome",
    "CPR": "cardiopulmonary resuscitation",
    "CABG": "coronary artery bypass grafting",
    "PCI": "percutaneous coronary intervention",
    "TPN": "total parenteral nutrition",
    "NG": "nasogastric",
    "PO": "per os (by mouth)",
    "QD": "once daily",
    "BID": "twice daily",
    "TID": "three times daily",
    "QID": "four times daily",
    "PRN": "as needed",
    "STAT": "immediately",
    "NPO": "nothing by mouth",
    "O2": "oxygen",
    "O2sat": "oxygen saturation",
    "BT": "body temperature",
    "RR": "respiratory rate",
    "TLC": "total lung capacity",
    "FVC": "forced vital capacity",
    "FEV1": "forced expiratory volume in 1 second",
    "MCH": "mean corpuscular hemoglobin",
    "MCHC": "mean corpuscular hemoglobin concentration",
    "MCV": "mean corpuscular volume",
    "MPV": "mean platelet volume",
    "PT": "prothrombin time",
    "PTT": "partial thromboplastin time",
    "INR": "international normalized ratio",
    "BNP": "brain natriuretic peptide",
    "NT-proBNP": "n-terminal pro brain natriuretic peptide",
    "TSH": "thyroid stimulating hormone",
    "T3": "triiodothyronine",
    "T4": "thyroxine",
    "ALT": "alanine aminotransferase",
    "AST": "aspartate aminotransferase",
    "ALP": "alkaline phosphatase",
    "GGT": "gamma glutamyl transferase",
    "BUN": "blood urea nitrogen",
    "Na": "sodium",
    "K": "potassium",
    "Cl": "chloride",
    "Ca": "calcium",
    "Mg": "magnesium",
    "Ph": "phosphate",
    "Hb": "hemoglobin",
    "Hct": "hematocrit",
    "PLT": "platelet",
    "ESR": "erythrocyte sedimentation rate",
    "LDH": "lactate dehydrogenase",
    "CPK": "creatine phosphokinase",
    "GFR": "glomerular filtration rate",
    "HBA1C": "hemoglobin A1c",
    "SIRS": "systemic inflammatory response syndrome",
    "MODS": "multiple organ dysfunction syndrome",
    "ARDS": "acute respiratory distress syndrome",
    "DVT": "deep vein thrombosis",
    "PE": "pulmonary embolism",
    "MI": "myocardial infarction",
    "CVA": "cerebrovascular accident",
    "TIA": "transient ischemic attack",
    "CHF": "congestive heart failure",
    "SOB": "shortness of breath",
    "HA": "headache",
    "LOC": "loss of consciousness",
    "RX": "prescription",
    "TX": "treatment",
    "DX": "diagnosis",
    "SX": "symptoms",
    "FX": "fracture",
    "HX": "history",
    "Sx": "surgery",
    "D/c": "discharge",
    "Adeno": "adenocarcinoma",
    "CXR": "chest x-ray",
    "KUB": "kidney ureter bladder x-ray",
    "ABG": "arterial blood gas",
    "LP": "lumbar puncture",
    "CSF": "cerebrospinal fluid",
    "GU": "genitourinary",
    "GI": "gastrointestinal",
    "CV": "cardiovascular",
    "MSK": "musculoskeletal",
    "Derm": "dermatology",
    "ENT": "ear nose throat",
    "OB": "obstetrics",
    "GYN": "gynecology",
    "Peds": "pediatrics",
    "Geris": "geriatrics",
    "Psych": "psychiatry",
    "ID": "infectious disease",
    "Onc": "oncology",
    "Neph": "nephrology",
    "Pulm": "pulmonology",
    "Rheum": "rheumatology",
    "Endo": "endocrinology",
    "Neuro": "neurology",
}


class AbbreviationLoader(BaseLoader):
    """Load medical abbreviations and their expansions from the abbreviation_list config.

    For each abbreviation in the config's `abbreviation_list`, creates two rows:
    - Row 1: the abbreviation itself (e.g., "ECG")
    - Row 2 (if expansion exists in ABBREVIATION_EXPANSION_MAP): the full expansion
      (e.g., "electrocardiogram")

    All abbreviations are marked `needs_review` since the expansion mapping is
    manual and abbreviations can have context-dependent meanings.
    """

    SOURCE_URL = "configs/term_inventory.yaml#abbreviation_list"

    def __init__(self, config: InventoryConfig):
        self.config = config
        self.abbreviation_list = config.abbreviation_list

    def load(self) -> pd.DataFrame:
        """Load abbreviation and expansion rows from the config list.

        Returns:
            DataFrame with MedicalTermRecord columns, two rows per abbreviation
            (abbreviation + expansion when available).
            Returns empty DataFrame with required columns if abbreviation_list is empty.
        """
        if not self.abbreviation_list:
            logger.info("abbreviation_list is empty — returning empty DataFrame.")
            return pd.DataFrame(columns=self.REQUIRED_COLS)

        rows: list[dict] = []
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        term_counter = 1

        for abbrev in self.abbreviation_list:
            abbrev = abbrev.strip()
            if not abbrev:
                continue

            # Row 1: the abbreviation itself
            rows.append({
                "term_id": f"term_{term_counter:06d}",
                "term_original": abbrev,
                "term_normalized": abbrev.lower().strip(),
                "entity_type": EntityType.ABBREVIATION.value,
                "medical_domain": None,
                "source_name": TermSource.ABBREVIATION_LIST.value,
                "source_url": self.SOURCE_URL,
                "source_license": None,
                "icd10_code": None,
                "rxnorm_rxcui": None,
                "is_code_switch_candidate": True,
                "review_status": ReviewStatus.NEEDS_REVIEW.value,
                "llm_generated_candidate": False,
                "fetched_at": now,
            })
            term_counter += 1

            # Row 2: the expansion (if known)
            expansion = ABBREVIATION_EXPANSION_MAP.get(abbrev)
            if expansion:
                rows.append({
                    "term_id": f"term_{term_counter:06d}",
                    "term_original": expansion,
                    "term_normalized": expansion.lower().strip(),
                    "entity_type": EntityType.ABBREVIATION.value,
                    "medical_domain": None,
                    "source_name": TermSource.ABBREVIATION_LIST.value,
                    "source_url": self.SOURCE_URL,
                    "source_license": None,
                    "icd10_code": None,
                    "rxnorm_rxcui": None,
                    "is_code_switch_candidate": True,
                    "review_status": ReviewStatus.NEEDS_REVIEW.value,
                    "llm_generated_candidate": False,
                    "fetched_at": now,
                })
                term_counter += 1

        if not rows:
            logger.warning("AbbreviationLoader produced 0 rows.")
            return pd.DataFrame(columns=self.REQUIRED_COLS)

        result = pd.DataFrame(rows)
        self._validate(result)

        abbrev_count = sum(
            1 for r in rows if r["term_original"] in self.abbreviation_list
        )
        expansion_count = len(rows) - abbrev_count
        logger.info(
            f"AbbreviationLoader loaded {len(result)} rows "
            f"({abbrev_count} abbreviations, {expansion_count} expansions)."
        )
        return result
