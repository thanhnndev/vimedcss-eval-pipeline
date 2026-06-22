"""openFDA medical device loader for Phase 6b.

Ingests medical device terms from the openFDA 510(k) device database.
openFDA is free, no API key required.

Base URL: https://api.fda.gov/device/510k.json
Query: GET ?search=device_name:"{query}"&limit=20
Rate limit: 1000 requests/day, 125/minute. Use 500ms delay between requests.
openFDA is an authoritative government database — terms are marked verified.
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

logger = setup_logger("openfda_device_loader")


class OpenFdaDeviceLoader(BaseLoader):
    """Ingest medical device terms from openFDA 510(k) device database.

    Each device category in the config is queried against the openFDA 510(k) API.
    Results are deduplicated by device_name (case-insensitive) and marked
    `verified` since openFDA is an authoritative government database.
    """

    BASE_URL = "https://api.fda.gov/device/510k.json"

    def __init__(self, config: InventoryConfig):
        self.config = config
        self.device_categories = config.openfda_device_categories
        self.delay_ms = 500  # openFDA rate limit: 500ms between requests

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
    )
    def _search_devices(self, query: str) -> list[dict]:
        """Search openFDA 510(k) API for device terms.

        Args:
            query: Search query (device name or category term).

        Returns:
            List of device record dicts with device_name and 510k_number.
            Returns empty list on failure (after all retries exhausted).
        """
        params = {"search": f'device_name:"{query}"', "limit": 20}
        try:
            response = httpx.get(self.BASE_URL, params=params, timeout=15.0)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error {e.response.status_code} for query={query!r}: {e}")
            return []
        except httpx.RequestError as e:
            logger.warning(f"Request error for query={query!r}: {e}")
            return []

        results = data.get("results", [])
        devices = []
        for record in results:
            device_name = record.get("device_name", "")
            if device_name and device_name.strip():
                devices.append({
                    "device_name": device_name.strip(),
                    "510k_number": record.get("510k_number", ""),
                })
        return devices

    def load(self) -> pd.DataFrame:
        """Load medical device terms from openFDA 510(k) API.

        Returns:
            DataFrame with MedicalTermRecord columns, one row per unique device.
            Returns empty DataFrame with required columns if no results found.
        """
        if not self.device_categories:
            logger.info("openfda_device_categories is empty — returning empty DataFrame.")
            return pd.DataFrame(columns=self.REQUIRED_COLS)

        rows: list[dict] = []
        seen_device_names: set[str] = set()  # deduplicate by lowercase name
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        term_counter = 1

        for category in self.device_categories:
            logger.debug(f"Searching openFDA 510(k) for category: {category!r}")
            devices = self._search_devices(category)

            if not devices:
                logger.debug(f"No results for category={category!r}")
                continue

            for device in devices:
                device_name = device["device_name"]
                device_name_lower = device_name.lower()
                if device_name_lower in seen_device_names:
                    continue
                seen_device_names.add(device_name_lower)

                rows.append({
                    "term_id": f"term_{term_counter:06d}",
                    "term_original": device_name,
                    "term_normalized": device_name_lower,
                    "entity_type": EntityType.DEVICE.value,
                    "medical_domain": None,
                    "source_name": TermSource.OPENFDA.value,
                    "source_url": (
                        f"{self.BASE_URL}?search=device_name:\"{category}\"&limit=20"
                    ),
                    "source_license": None,
                    "icd10_code": None,
                    "rxnorm_rxcui": None,
                    "is_code_switch_candidate": True,
                    "review_status": ReviewStatus.VERIFIED.value,
                    "llm_generated_candidate": False,
                    "fetched_at": now,
                    # Extra column for device-specific data
                    "openfda_device_number": device["510k_number"] or None,
                })

                term_counter += 1

            time.sleep(self.delay_ms / 1000.0)

        if not rows:
            logger.warning(
                "OpenFdaDeviceLoader returned 0 rows. "
                "Check network connectivity or verify openFDA API is accessible."
            )
            return pd.DataFrame(columns=self.REQUIRED_COLS)

        result = pd.DataFrame(rows)
        self._validate(result)
        logger.info(
            f"OpenFdaDeviceLoader loaded {len(result)} unique device terms "
            f"from {len(self.device_categories)} categories."
        )
        return result
