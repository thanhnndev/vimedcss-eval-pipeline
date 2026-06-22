"""NLM lab test and procedure loader for Phase 6b.

Ingests lab test and procedure terms from the NLM ICD-10-CM Clinical Table Search API.
Used for lab_test and procedure entity types.

API is free, no license required.
Base URL: https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search
Query: GET ?sf=code,name&terms={query}&limit=10
Response: data[0] = match count, data[3] = list of [code, name] pairs
Rate limit: 200ms between requests.
"""
import time
from datetime import datetime, timezone

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_fixed

from src.term_inventory.loaders.icd10_backbone import BaseLoader
from src.term_inventory.schemas import (
    EntityType,
    InventoryConfig,
    ReviewStatus,
    TermSource,
)
from src.shared.logging import setup_logger

logger = setup_logger("nlm_lab_loader")

# Keywords to classify a term as a lab test vs. procedure
LAB_TEST_KEYWORDS = {"test", "level", "count", "panel", "glucose", "cholesterol",
                     "hemoglobin", "creatinine", "bilirubin", "albumin", "protein",
                     "electrolyte", "urea", "triglyceride", "hba1c", "hba1c",
                     "enzyme", "antibody", "antigen", "assay", "scan", "imaging"}

PROCEDURE_KEYWORDS = {"surgery", "biopsy", "dialysis", "chemotherapy", "radiotherapy",
                      "angiography", "endoscopy", "colonoscopy", "ultrasound",
                      "x-ray", "xray", "mri", "ct scan", "catheter", "transplant",
                      "amputation", "resection", "incision", "drainage", "dressing"}


class NlmLabLoader(BaseLoader):
    """Ingest lab test and procedure terms from NLM ICD-10-CM Clinical Table Search API.

    Two seed lists are searched:
    - Lab test seeds: common lab test names (e.g., "complete blood count", "glucose")
    - Procedure seeds: common procedure names (e.g., "x-ray", "ultrasound", "MRI scan")

    Each result is classified as either lab_test or procedure based on keyword matching
    against the term name. Results are marked `needs_review` — NLM ICD-10-CM is a
    general-purpose classification system, not a dedicated lab/procedure authority.
    """

    BASE_URL = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"

    # Seed search terms for lab tests
    LAB_TEST_SEEDS = [
        "complete blood count", "glucose", "cholesterol", "hemoglobin",
        "creatinine", "thyroid", "liver function", "kidney function",
        "HbA1c", "bilirubin", "albumin", "protein", "electrolyte",
        "uric acid", "triglyceride", "HDL", "LDL", "blood sugar",
        "blood glucose", "liver panel", "kidney panel", "lipid panel",
        "thyroid panel", "CBC", "urinalysis", "WBC count", "RBC count",
        "platelet count", "hemoglobin A1c", "prothrombin time", "INR",
    ]

    # Seed search terms for procedures
    PROCEDURE_SEEDS = [
        "x-ray", "ultrasound", "MRI scan", "CT scan", "endoscopy",
        "biopsy", "surgery", "dialysis", "chemotherapy", "radiotherapy",
        "angiography", "echocardiography", "colonoscopy", "mammography",
        "PET scan", "SPECT scan", "catheterization", "pacemaker",
        "intubation", "tracheostomy", "laparoscopy", "arthroscopy",
        "bronchoscopy", "lumbar puncture", "thoracentesis", "paracentesis",
    ]

    def __init__(self, config: InventoryConfig):
        self.config = config
        self.delay_ms = 200  # NLM rate limit

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
    )
    def _search_icd10cm(self, query: str) -> list[tuple[str, str]]:
        """Search NLM ICD-10-CM API for a query term.

        Args:
            query: Search term (e.g., "glucose", "x-ray").

        Returns:
            List of (code, name) tuples from the API.
            Returns empty list on failure (after all retries exhausted).
        """
        params = {"sf": "code,name", "terms": query, "limit": 10}
        try:
            response = httpx.get(self.BASE_URL, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error {e.response.status_code} for query={query!r}: {e}")
            return []
        except httpx.RequestError as e:
            logger.warning(f"Request error for query={query!r}: {e}")
            return []

        # data[0] = match count, data[3] = list of [code, name] pairs
        try:
            results = data.get("data", [])
            if len(results) < 4:
                return []
            entries = results[3] or []
            return [(entry[0], entry[1]) for entry in entries if len(entry) >= 2]
        except (IndexError, TypeError) as e:
            logger.warning(f"Failed to parse NLM response for query={query!r}: {e}")
            return []

    def _classify_entity_type(self, term_name: str) -> str:
        """Classify a term as lab_test or procedure based on keywords."""
        name_lower = term_name.lower()
        for kw in LAB_TEST_KEYWORDS:
            if kw in name_lower:
                return EntityType.LAB_TEST.value
        for kw in PROCEDURE_KEYWORDS:
            if kw in name_lower:
                return EntityType.PROCEDURE.value
        # Default to procedure for ambiguous terms
        return EntityType.PROCEDURE.value

    def load(self) -> pd.DataFrame:
        """Load lab test and procedure terms from NLM ICD-10-CM API.

        Returns:
            DataFrame with MedicalTermRecord columns, one row per term.
            Returns empty DataFrame with required columns if no results found.
        """
        all_seeds = self.LAB_TEST_SEEDS + self.PROCEDURE_SEEDS
        if not all_seeds:
            logger.info("No seed terms configured — returning empty DataFrame.")
            return pd.DataFrame(columns=self.REQUIRED_COLS)

        rows: list[dict] = []
        seen_terms: set[str] = set()  # deduplicate by normalized name
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        term_counter = 1
        lab_test_count = 0
        procedure_count = 0

        for seed in all_seeds:
            logger.debug(f"Searching NLM ICD-10-CM for: {seed!r}")
            results = self._search_icd10cm(seed)

            if not results:
                logger.debug(f"No results for seed={seed!r}")
                continue

            for code, name in results:
                term_normalized = name.lower().strip()
                if term_normalized in seen_terms:
                    continue
                seen_terms.add(term_normalized)

                entity_type = self._classify_entity_type(name)

                rows.append({
                    "term_id": f"term_{term_counter:06d}",
                    "term_original": name,
                    "term_normalized": term_normalized,
                    "entity_type": entity_type,
                    "medical_domain": None,
                    "source_name": TermSource.NLM_LAB.value,
                    "source_url": f"{self.BASE_URL}?sf=code,name&terms={seed}&limit=10",
                    "source_license": None,
                    "icd10_code": code or None,
                    "rxnorm_rxcui": None,
                    "is_code_switch_candidate": True,
                    "review_status": ReviewStatus.NEEDS_REVIEW.value,
                    "llm_generated_candidate": False,
                    "fetched_at": now,
                })

                if entity_type == EntityType.LAB_TEST.value:
                    lab_test_count += 1
                else:
                    procedure_count += 1

                term_counter += 1

            time.sleep(self.delay_ms / 1000.0)

        if not rows:
            logger.warning(
                "NlmLabLoader returned 0 rows. "
                "Check network connectivity or verify NLM API is accessible."
            )
            return pd.DataFrame(columns=self.REQUIRED_COLS)

        result = pd.DataFrame(rows)
        self._validate(result)

        logger.info(
            f"NlmLabLoader loaded {len(result)} terms "
            f"({lab_test_count} lab_test, {procedure_count} procedure) "
            f"from {len(all_seeds)} seed queries."
        )
        return result
