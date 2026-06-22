"""RxNorm drug loader for Phase 6b.

Ingests drug terms from the NLM RxNorm REST API using a seed drug name list.
RxNorm is free, no license required. Rate limit: 200ms between requests.

API base URL: https://rxnav.nlm.nih.gov/REST
Relevant endpoints:
  - GET /drugs.json?name=<drug_name> — get drug concepts by name
  - Returns drugGroup → conceptGroup → conceptProperties with name, rxcui, tty
TTY filter: only accept SCD (Semantic Clinical Drug), IN (Ingredient), BN (Brand Name).
"""
import time
from datetime import datetime, timezone

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_fixed

from src.shared.logging import setup_logger
from src.term_inventory.loaders.icd10_backbone import BaseLoader
from src.term_inventory.schemas import (
    EntityType,
    InventoryConfig,
    ReviewStatus,
    TermSource,
)

logger = setup_logger("rxnorm_loader")


class RxNormLoader(BaseLoader):
    """Ingest drug terms from NLM RxNorm REST API.

    Each seed drug name in the config is queried against the RxNorm API.
    Results are filtered to clinically useful TTY values and mapped to
    MedicalTermRecord schema. RxNorm is authoritative — terms are marked verified.
    """

    BASE_URL = "https://rxnav.nlm.nih.gov/REST"

    # TTY values that represent clinically useful drug concepts
    USEFUL_TTY = {"SCD", "IN", "BN"}

    def __init__(self, config: InventoryConfig):
        self.config = config
        self.drug_list = config.rxnorm_drug_list
        self.delay_ms = 200  # NLM rate limit: minimum gap between requests

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
    )
    def _fetch_drug_concepts(self, drug_name: str) -> list[dict]:
        """Fetch drug concepts for a single drug name with retry.

        Args:
            drug_name: drug name to query (case-insensitive on server side).

        Returns:
            List of concept dicts with keys: name, rxcui, tty.
            Returns empty list on failure (after all retries exhausted).
        """
        url = f"{self.BASE_URL}/drugs.json"
        try:
            response = httpx.get(url, params={"name": drug_name}, timeout=10.0)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error {e.response.status_code} for drug={drug_name!r}: {e}")
            return []
        except httpx.RequestError as e:
            logger.warning(f"Request error for drug={drug_name!r}: {e}")
            return []

        concepts = []
        drug_group = data.get("drugGroup", {})
        for concept_group in drug_group.get("conceptGroup", []):
            for concept in concept_group.get("conceptProperties", []):
                tty = concept.get("tty", "")
                if tty in self.USEFUL_TTY:
                    concepts.append({
                        "name": concept.get("name", ""),
                        "rxcui": concept.get("rxcui", ""),
                        "tty": tty,
                    })

        return concepts

    def load(self) -> pd.DataFrame:
        """Load drug terms from RxNorm for all configured seed drug names.

        Returns:
            DataFrame with MedicalTermRecord columns, one row per drug concept.
            Returns empty DataFrame with required columns if drug_list is empty.
        """
        if not self.drug_list:
            logger.info("rxnorm_drug_list is empty — returning empty DataFrame.")
            result = pd.DataFrame(columns=self.REQUIRED_COLS)
            return result

        rows: list[dict] = []
        seen_rxcuis: set[str] = set()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        term_counter = 1

        for drug_name in self.drug_list:
            logger.debug(f"Fetching RxNorm concepts for {drug_name!r}")
            concepts = self._fetch_drug_concepts(drug_name)

            if not concepts:
                logger.warning(f"No RxNorm concepts found for drug={drug_name!r}")
                continue

            for concept in concepts:
                rxcui = concept["rxcui"]
                # Deduplicate by RxCUI across seed names (same drug may appear multiple times)
                if rxcui in seen_rxcuis:
                    continue
                seen_rxcuis.add(rxcui)

                term_name = concept["name"]
                rows.append({
                    "term_id": f"term_{term_counter:06d}",
                    "term_original": term_name,
                    "term_normalized": term_name.lower().strip(),
                    "entity_type": EntityType.DRUG.value,
                    "medical_domain": None,
                    "source_name": TermSource.RXNORM.value,
                    "source_url": f"{self.BASE_URL}/drugs.json?name={drug_name}",
                    "source_license": "NLM RxNorm — public domain",
                    "icd10_code": None,
                    "rxnorm_rxcui": rxcui,
                    "is_code_switch_candidate": True,
                    "review_status": ReviewStatus.VERIFIED.value,
                    "llm_generated_candidate": False,
                    "fetched_at": now,
                })
                term_counter += 1

            time.sleep(self.delay_ms / 1000.0)

        if not rows:
            logger.warning(
                "RxNormLoader returned 0 rows. "
                "Check network connectivity or verify drug names are valid RxNorm concepts."
            )
            return pd.DataFrame(columns=self.REQUIRED_COLS)

        result = pd.DataFrame(rows)
        self._validate(result)
        logger.info(
            f"RxNormLoader loaded {len(result)} unique drug concepts "
            f"from {len(self.drug_list)} seed names."
        )
        return result
