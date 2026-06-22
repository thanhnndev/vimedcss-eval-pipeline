"""LLM-assisted term classification for Phase 6b medical term inventory.

Only non-authoritative source terms (vimedcss_seed, abbreviation_list, nlm_lab)
are sent to LLM for entity_type and medical_domain classification.
Authoritative sources (icd10, rxnorm, openfda) already carry entity metadata.
"""
import json
import os
import time
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_fixed

from src.shared.logging import setup_logger
from src.term_inventory.schemas import (
    EntityType,
    InventoryConfig,
    ReviewStatus,
    TermSource,
)

logger = setup_logger("term_inventory.classifier")

# Authoritative sources that already carry entity metadata — skip LLM classification
AUTHORITATIVE_SOURCES: set[str] = {
    TermSource.ICD10.value,
    TermSource.RXNORM.value,
    TermSource.OPENFDA.value,
}

# FR2-04 entity types (14 values)
ENTITY_TYPES_LIST = [e.value for e in EntityType]

# Medical domains
MEDICAL_DOMAINS = [
    "Medical Sciences",
    "Pathology & Pathogens",
    "Treatments",
    "Nutrition",
    "Diagnostics",
    "unknown",
]


class MedicalTermClassifier:
    """Classifies non-authoritative medical terms using OpenAI structured outputs.

    Only non-authoritative terms (vimedcss_seed, abbreviation_list, nlm_lab) are sent
    to the LLM. Authoritative source terms (icd10, rxnorm, openfda) preserve their
    existing entity_type. All LLM-classified terms get:
    - llm_generated_candidate=True
    - review_status=not_verified
    - needs_human_review=True if confidence < 0.80
    """

    def __init__(self, config: InventoryConfig, *, mock: bool = False):
        self.config = config
        self.confidence_threshold = config.confidence_threshold
        self.output_dir = config.output_dir
        self.log_dir = config.log_dir

        # Load LLM config from configs/llm.yaml
        llm_cfg_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "configs",
            "llm.yaml",
        )
        if os.path.exists(llm_cfg_path):
            with open(llm_cfg_path, encoding="utf-8") as f:
                llm_cfg = yaml.safe_load(f)
            self.llm_model = llm_cfg.get("model", "gpt-4o-mini")
            self.batch_size = llm_cfg.get("batch_size", 25)
            self.max_retries = llm_cfg.get("max_retries", 3)
        else:
            self.llm_model = "gpt-4o-mini"
            self.batch_size = 25
            self.max_retries = 3

        # Mock mode: no API key needed
        self._mock_mode = mock
        self._client: Optional[OpenAI] = None

        if not mock:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError(
                    "OPENAI_API_KEY environment variable is required for live LLM classification. "
                    "Use mock=True for smoke tests without an API key."
                )
            self._client = OpenAI(api_key=api_key)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def classify(self, df: pd.DataFrame) -> pd.DataFrame:
        """Classify non-authoritative terms and update the DataFrame in-place.

        Args:
            df: DataFrame with columns: term_id, term_original, term_normalized,
                entity_type, medical_domain, source_name, review_status,
                llm_generated_candidate, needs_human_review.

        Returns:
            Updated DataFrame with entity_type, medical_domain, llm_generated_candidate,
            review_status, needs_human_review filled for non-authoritative terms.
        """
        df = df.copy()

        # Identify authoritative rows — these are NOT sent to LLM
        authoritative_mask = df["source_name"].isin(AUTHORITATIVE_SOURCES)
        non_auth_df = df[~authoritative_mask].copy()

        if non_auth_df.empty:
            logger.info(
                "No non-authoritative terms to classify. "
                f"All {len(df)} terms are from authoritative sources."
            )
            return df

        n_non_auth = len(non_auth_df)
        n_sources = non_auth_df["source_name"].nunique()
        logger.info(
            f"Classifying {n_non_auth} non-authoritative terms from {n_sources} sources."
        )

        # Batch non-authoritative terms for LLM classification
        all_results: List[Dict[str, Any]] = []
        terms_for_classification: List[Dict[str, Any]] = []

        for _, row in non_auth_df.iterrows():
            terms_for_classification.append({
                "term_original": str(row.get("term_original", "")),
                "term_id": str(row.get("term_id", "")),
                "source_name": str(row.get("source_name", "")),
            })

        # Classify in batches
        for i in range(0, len(terms_for_classification), self.batch_size):
            batch = terms_for_classification[i:i + self.batch_size]
            batch_results = self._classify_batch(batch)
            all_results.extend(batch_results)

        # Build lookup: term_original → classification result
        results_lookup = {r["term_original"]: r for r in all_results}

        # Apply classification results back to DataFrame
        for idx, row in df.iterrows():
            if row["source_name"] in AUTHORITATIVE_SOURCES:
                # Authoritative — keep as-is
                continue

            term_original = str(row.get("term_original", ""))
            cls_result = results_lookup.get(term_original)

            if cls_result:
                df.at[idx, "entity_type"] = cls_result["entity_type"]
                df.at[idx, "medical_domain"] = cls_result["medical_domain"]
                df.at[idx, "llm_generated_candidate"] = True
                df.at[idx, "review_status"] = ReviewStatus.NOT_VERIFIED
                df.at[idx, "needs_human_review"] = cls_result["needs_human_review"]
            else:
                # Fallback: mark as needing review
                df.at[idx, "llm_generated_candidate"] = True
                df.at[idx, "review_status"] = ReviewStatus.NOT_VERIFIED
                df.at[idx, "needs_human_review"] = True

        n_classified = (~df["llm_generated_candidate"]).sum()
        n_llm_candidates = df["llm_generated_candidate"].sum()
        logger.info(
            f"Classification complete: {n_classified} authoritative preserved, "
            f"{n_llm_candidates} LLM-classified candidates."
        )

        return df

    # -------------------------------------------------------------------------
    # LLM API (private)
    # -------------------------------------------------------------------------

    def _classify_batch(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Classify a batch of terms via OpenAI structured outputs or mock mode."""
        if self._mock_mode:
            return self._mock_classify_batch(batch)

        return self._llm_classify_batch(batch)

    def _llm_classify_batch(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Call OpenAI API with structured output for batch classification."""
        from src.term_inventory.schemas import (
            InventoryClassificationBatchResponse,
        )

        user_payload = json.dumps(
            {
                "task": "classify_vimedcss_inventory_terms",
                "terms": [
                    {"term_original": b["term_original"]} for b in batch
                ],
            },
            ensure_ascii=False,
        )

        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            model = self.llm_model if attempt == 0 else "gpt-4o-mini"
            try:
                start_time = time.time()
                is_reasoning = model.startswith(("o1", "o3", "gpt-5"))

                api_kwargs: Dict[str, Any] = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": self._build_system_prompt()},
                        {"role": "user", "content": user_payload},
                    ],
                    "response_format": InventoryClassificationBatchResponse,
                }
                if is_reasoning:
                    api_kwargs["reasoning_effort"] = "medium"
                else:
                    api_kwargs["temperature"] = 0.0

                request_payload = {
                    "model": model,
                    "messages": api_kwargs["messages"],
                    "response_format": "InventoryClassificationBatchResponse",
                }
                if is_reasoning:
                    request_payload["reasoning_effort"] = "medium"
                else:
                    request_payload["temperature"] = 0.0

                completion = self._client.beta.chat.completions.parse(**api_kwargs)
                duration = time.time() - start_time

                parsed = completion.choices[0].message.parsed
                if not parsed:
                    raise ValueError("Failed to parse response into Pydantic model.")

                response_payload = {
                    "id": completion.id,
                    "model": completion.model,
                    "choices": [{
                        "finish_reason": completion.choices[0].finish_reason,
                        "usage": completion.usage.model_dump() if completion.usage else {},
                    }],
                    "duration_seconds": duration,
                }

                self._log_audit(request_payload, response_payload)

                return [
                    {
                        "term_original": item.term_original,
                        "entity_type": item.entity_type,
                        "medical_domain": item.medical_domain,
                        "confidence": item.confidence,
                        "needs_human_review": item.needs_human_review,
                        "evidence": item.evidence,
                        "uncertainty_reason": item.uncertainty_reason,
                    }
                    for item in parsed.items
                ]

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                last_error = e
                time.sleep(2 ** attempt)

        logger.error(f"All {self.max_retries} API attempts failed: {last_error}")
        # Fall back to mock for this batch
        return self._mock_classify_batch(batch)

    @staticmethod
    def _build_system_prompt() -> str:
        """Vietnamese system prompt for entity_type and medical_domain classification."""
        return (
            "Bạn là bộ phân loại thuật ngữ y tế chuyên nghiệp cho dự án nghiên cứu ViMedCSS.\n"
            "Nhiệm vụ: Phân loại các thuật ngữ y tế tiếng Anh theo entity_type và medical_domain.\n\n"
            "Entity types (FR2-04, 14 giá trị):\n"
            + ", ".join(ENTITY_TYPES_LIST) + "\n\n"
            "Medical domains (Lớp 1):\n"
            + ", ".join(MEDICAL_DOMAINS) + "\n\n"
            "Quy tắc:\n"
            "1. Chỉ phân loại entity_type và medical_domain; không bịa đặt nguồn.\n"
            "2. Đánh giá độ tin cậy (confidence) từ 0.0 đến 1.0.\n"
            "3. Nếu confidence < 0.80 hoặc có sự mơ hồ lớn, đặt needs_human_review = true.\n"
            "4. Trả về kết quả JSON hợp lệ theo schema InventoryClassificationBatchResponse.\n"
        )

    # -------------------------------------------------------------------------
    # Mock classification (no API key required)
    # -------------------------------------------------------------------------

    def _mock_classify_batch(
        self, batch: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Keyword-based mock classification for smoke tests."""
        results = []
        for item in batch:
            term = item["term_original"].lower()
            term_lower = term.lower()

            # Keyword-based entity_type classification
            if any(k in term_lower for k in [
                "metformin", "insulin", "aspirin", "stent", "drug",
                "paracetamol", "atorvastatin", "losartan", "amlodipine",
                "omeprazole", "lisinopril", "simvastatin", "warfarin",
                "clopidogrel", "levothyroxine", "prednisone", "hba1c",
                "cholesterol", "triglyceride",
            ]):
                if "stent" in term_lower:
                    entity_type = EntityType.DEVICE
                else:
                    entity_type = EntityType.DRUG
            elif any(k in term_lower for k in [
                "diabetes", "asthma", "hepatitis", "cancer", "hypertension",
                "disease", "pathology", "tumor", "carcinoma", "fibrosis",
            ]):
                entity_type = EntityType.DISEASE
            elif any(k in term_lower for k in [
                "hba1c", "crp", "egfr", "ast", "alt", "test", "glucose",
                "cholesterol", "biomarker", "hemoglobin", "creatinine",
                "urea", "albumin", "bilirubin", "albumin", "electrolyte",
            ]):
                if "cholesterol" in term_lower:
                    entity_type = EntityType.LAB_TEST
                else:
                    entity_type = EntityType.LAB_TEST
            elif any(k in term_lower for k in [
                "ct", "mri", "endoscopy", "scan", "ultrasound", "surgery",
                "biopsy", "dialysis", "transplant", "x-ray",
            ]):
                entity_type = EntityType.PROCEDURE
            elif any(k in term_lower for k in [
                "thyroid", "liver", "kidney", "heart", "lung", "brain",
                "spine", "bone", "artery", "vein", "muscle", "nerve",
            ]):
                entity_type = EntityType.ANATOMY
            elif any(k in term_lower for k in [
                "estrogen", "renin", "thyroxine", "testosterone", "cortisol",
                "insulin", "adrenaline", "progesterone", "growth hormone",
            ]):
                entity_type = EntityType.HORMONE
            elif any(k in term_lower for k in [
                "virus", "bacteria", "helicobacter", "e. coli", "covid",
                "infection", "pathogen", "staphylococcus", "streptococcus",
            ]):
                entity_type = EntityType.PATHOGEN
            elif any(k in term_lower for k in [
                "vitamin", "supplement", "calcium", "iron", "zinc", "magnesium",
                "nutrient", "protein", "fiber", "electrolyte",
            ]):
                entity_type = EntityType.BIOMARKER
            elif len(term) <= 5 and term.isupper():
                entity_type = EntityType.ABBREVIATION
            elif any(k in term_lower for k in [
                "ecg", "eeg", "icu", "iv", "im", "bp", "hr", "wbc",
                "rbc", "copd", "uti", "gerd", "hiv", "aids", "copd",
                "cpr", "ct", "mri",
            ]):
                entity_type = EntityType.ABBREVIATION
            elif any(k in term_lower for k in [
                "device", "monitor", "sensor", "pump", "catheter", "implant",
            ]):
                entity_type = EntityType.DEVICE
            elif any(k in term_lower for k in [
                "mg", "ml", "g", "kg", "mcg", "l", "meq", "iu", "unit",
            ]):
                entity_type = EntityType.UNIT
            elif any(k in term_lower for k in [
                "fever", "pain", "cough", "nausea", "fatigue", "dizziness",
                "headache", "symptom", "swelling", "inflammation",
            ]):
                entity_type = EntityType.SYMPTOM
            else:
                entity_type = EntityType.UNKNOWN

            # Keyword-based medical_domain
            if any(k in term_lower for k in [
                "diabetes", "hba1c", "insulin", "thyroid", "renin",
                "metformin", "cortisol", "estrogen", "testosterone",
            ]):
                medical_domain = "endocrinology"
            elif any(k in term_lower for k in [
                "heart", "cardio", "stent", "ecg", "hypertension",
                "cholesterol", "triglyceride", "atrial", "ventricular",
            ]):
                medical_domain = "cardiology"
            elif any(k in term_lower for k in [
                "asthma", "lung", "respiratory", "bronchitis", "copd",
                "pneumonia", "tb", "tuberculosis",
            ]):
                medical_domain = "pulmonology"
            elif any(k in term_lower for k in [
                "virus", "bacteria", "covid", "hepatitis", "infection",
                "helicobacter", "staphylococcus", "streptococcus",
            ]):
                medical_domain = "infectious_disease"
            elif any(k in term_lower for k in [
                "liver", "hepatology", "alt", "ast", "bilirubin", "hepatic",
            ]):
                medical_domain = "hepatology"
            elif any(k in term_lower for k in [
                "kidney", "nephrology", "egfr", "creatinine", "urea",
                "dialysis", "renal",
            ]):
                medical_domain = "nephrology"
            elif any(k in term_lower for k in [
                "cancer", "oncology", "tumor", "carcinoma", "chemotherapy",
                "malignant",
            ]):
                medical_domain = "oncology"
            elif any(k in term_lower for k in [
                "mri", "ct", "radiology", "ultrasound", "x-ray", "scan",
                "imaging",
            ]):
                medical_domain = "radiology"
            elif any(k in term_lower for k in [
                "test", "crp", "cbc", "glucose", "hemoglobin", "albumin",
                "laboratory", "biomarker", "electrolyte",
            ]):
                medical_domain = "laboratory_medicine"
            elif any(k in term_lower for k in [
                "surgery", "biopsy", "endoscopy", "transplant",
            ]):
                medical_domain = "surgery"
            elif any(k in term_lower for k in [
                "vitamin", "nutrition", "supplement", "nutrient",
                "calcium", "iron", "protein",
            ]):
                medical_domain = "nutrition"
            elif entity_type == EntityType.DISEASE:
                medical_domain = "Medical Sciences"
            elif entity_type == EntityType.PATHOGEN:
                medical_domain = "Pathology & Pathogens"
            elif entity_type == EntityType.DRUG:
                medical_domain = "Treatments"
            elif entity_type == EntityType.LAB_TEST:
                medical_domain = "Diagnostics"
            else:
                medical_domain = "unknown"

            confidence = 0.95 if entity_type != EntityType.UNKNOWN else 0.50
            needs_human_review = confidence < self.confidence_threshold

            results.append({
                "term_original": item["term_original"],
                "entity_type": entity_type,
                "medical_domain": medical_domain,
                "confidence": confidence,
                "needs_human_review": needs_human_review,
                "evidence": "Mock classification based on keyword matching.",
                "uncertainty_reason": (
                    "Low confidence mock mapping" if needs_human_review else None
                ),
            })

        # Log mock audit
        mock_request = {
            "task": "mock_classification",
            "count": len(batch),
            "batch_size": self.batch_size,
        }
        mock_response = {"status": "success", "items": results}
        self._log_audit(mock_request, mock_response)

        return results

    # -------------------------------------------------------------------------
    # Audit logging
    # -------------------------------------------------------------------------

    def _log_audit(self, request: Dict[str, Any], response: Dict[str, Any]) -> None:
        """Append a JSONL audit record to logs/term_inventory_classification_audit.jsonl."""
        os.makedirs(self.log_dir, exist_ok=True)
        audit_path = os.path.join(self.log_dir, "term_inventory_classification_audit.jsonl")
        record = {
            "request": request,
            "response": response,
        }
        with open(audit_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
