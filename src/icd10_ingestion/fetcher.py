import time
import httpx
import logging
from typing import Dict, List, Literal

from tenacity import retry, stop_after_attempt, wait_exponential, RetryError

from src.icd10_ingestion.schemas import ICD10ErrorRecord

logger = logging.getLogger("icd10_ingestion.fetcher")


class ICD10Fetcher:
    """HTTP client for the KCB ICD-10 API with rate limiting and retry logic."""

    def __init__(
        self,
        rate_limit_ms: int = 200,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_multiplier: float = 1.0,
        backoff_min: float = 1.0,
        backoff_max: float = 10.0,
    ):
        self.rate_limit_ms = rate_limit_ms
        self.base_url = "https://ccs.whiteneuron.com/api/ICD10"
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_multiplier = backoff_multiplier
        self.backoff_min = backoff_min
        self.backoff_max = backoff_max
        self.client = httpx.Client(timeout=timeout)
        self.stats = {
            "total_requests": 0,
            "total_failures": 0,
            "by_language": {"en": 0, "vi": 0},
        }
        self._errors: List[ICD10ErrorRecord] = []

    def get_source_url(self, code: str, language: str) -> str:
        """Return the exact URL string used for a request."""
        return (
            f"{self.base_url}/search/{httpx.URL(code).path}"
            f"?lang={language}&vol1=1&vol3=0&html=true"
        )

    def _build_url(self, code: str, language: str) -> str:
        encoded = httpx.URL(code).path
        return f"{self.base_url}/search/{encoded}?lang={language}&vol1=1&vol3=0&html=true"

    def _log_error(self, code: str, language: str, exc: Exception, attempt: int) -> None:
        from datetime import datetime, timezone

        error_type = "timeout" if isinstance(exc, httpx.TimeoutException) else "http_error"
        self._errors.append(
            ICD10ErrorRecord(
                code=code,
                language=language,  # type: ignore
                error_type=error_type,
                error_message=str(exc),
                attempt=attempt,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )
        logger.warning(f"[{code}/{language}] Error on attempt {attempt}: {exc}")

    def fetch(self, code: str, language: Literal["en", "vi"]) -> httpx.Response:
        """Fetch a single ICD-10 code in the specified language.

        Retries on failure with exponential back-off and records errors.
        """
        url = self._build_url(code, language)
        self.stats["total_requests"] += 1
        self.stats["by_language"][language] += 1

        attempt = 1
        last_exc: Exception | None = None

        while attempt <= self.max_retries:
            try:
                response = self.client.get(url)
                response.raise_for_status()
                time.sleep(self.rate_limit_ms / 1000)
                return response
            except httpx.HTTPStatusError as e:
                last_exc = e
                self._log_error(code, language, e, attempt)
                if attempt < self.max_retries:
                    wait = min(
                        self.backoff_multiplier * (2 ** (attempt - 1)),
                        self.backoff_max,
                    )
                    wait = max(wait, self.backoff_min)
                    logger.info(f"[{code}/{language}] Retrying in {wait:.1f}s...")
                    time.sleep(wait)
                attempt += 1
            except httpx.TimeoutException as e:
                last_exc = e
                self._log_error(code, language, e, attempt)
                if attempt < self.max_retries:
                    wait = min(
                        self.backoff_multiplier * (2 ** (attempt - 1)),
                        self.backoff_max,
                    )
                    wait = max(wait, self.backoff_min)
                    logger.info(f"[{code}/{language}] Retrying in {wait:.1f}s...")
                    time.sleep(wait)
                attempt += 1
            except httpx.RequestError as e:
                last_exc = e
                self._log_error(code, language, e, attempt)
                if attempt < self.max_retries:
                    wait = min(
                        self.backoff_multiplier * (2 ** (attempt - 1)),
                        self.backoff_max,
                    )
                    wait = max(wait, self.backoff_min)
                    logger.info(f"[{code}/{language}] Retrying in {wait:.1f}s...")
                    time.sleep(wait)
                attempt += 1

        self.stats["total_failures"] += 1
        if last_exc:
            raise last_exc
        raise RuntimeError(f"Failed to fetch {code}/{language} after {self.max_retries} attempts")

    def fetch_many(
        self, codes: List[str], language: Literal["en", "vi"]
    ) -> Dict[str, httpx.Response]:
        """Fetch multiple ICD-10 codes, returning a dict of code -> response.

        Errors are logged to self._errors and excluded from the result dict.
        """
        results: Dict[str, httpx.Response] = {}
        for code in codes:
            try:
                response = self.fetch(code, language)
                results[code] = response
            except Exception as exc:
                logger.error(f"[{code}/{language}] All retries exhausted: {exc}")
                self.stats["total_failures"] += 1
        return results

    def get_errors(self) -> List[ICD10ErrorRecord]:
        """Return all recorded error records."""
        return list(self._errors)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self.client.close()
