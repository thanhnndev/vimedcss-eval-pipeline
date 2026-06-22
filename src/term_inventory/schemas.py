"""Phase 6b: Medical Term Inventory Schemas.

This module defines the core Pydantic models for the multi-source medical term inventory.
It includes:
- EntityType: 14-category taxonomy for medical entity classification (FR2-04)
- ReviewStatus: verification state for each term record
- TermSource: named provenance sources (ICD-10, RxNorm, openFDA, etc.)
- MedicalTermRecord: full provenance-tracked term record
- InventoryConfig: configuration for the inventory build pipeline
- Phase2ToFr2EntityTypeMap: backward-compatibility mapping from Phase 2 EntityCategory
"""
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    """FR2-04 entity type taxonomy (14 values).

    Differentiated from Phase 2's EntityCategory enum by naming convention
    (snake_case vs underscores) and scope (14 types vs 13 categories).
    The Phase2ToFr2EntityTypeMap provides backward-compatibility mapping.
    """
    DISEASE = "disease"
    DRUG = "drug"
    LAB_TEST = "lab_test"
    PROCEDURE = "procedure"
    ANATOMY = "anatomy"
    SYMPTOM = "symptom"
    ABBREVIATION = "abbreviation"
    HORMONE = "hormone"
    BIOMARKER = "biomarker"
    PATHOGEN = "pathogen"
    DEVICE = "device"
    UNIT = "unit"
    DOSAGE = "dosage"
    UNKNOWN = "unknown"


class ReviewStatus(str, Enum):
    """Verification status for a term record.

    - verified: authoritative source confirmed the term (ICD-10, RxNorm, etc.)
    - llm_candidate: LLM-generated candidate without external verification
    - not_verified: no verification attempted
    - needs_review: human review required before inclusion
    """
    VERIFIED = "verified"
    LLM_CANDIDATE = "llm_candidate"
    NOT_VERIFIED = "not_verified"
    NEEDS_REVIEW = "needs_review"


class TermSource(str, Enum):
    """Named provenance sources for term ingestion.

    Every MedicalTermRecord must have a non-unknown source_name.
    """
    ICD10 = "icd10"
    RXNORM = "rxnorm"
    OPENFDA = "openfda"
    VIMEDCSS_SEED = "vimedcss_seed"
    NLM_LAB = "nlm_lab"
    ABBREVIATION_LIST = "abbreviation_list"
    LLM_GENERATED = "llm_generated"
    UNKNOWN = "unknown"


# Phase 2 EntityCategory → FR2-04 EntityType mapping for backward compatibility
Phase2ToFr2EntityTypeMap: Dict[str, EntityType] = {
    "disease_or_condition": EntityType.DISEASE,
    "drug_or_active_ingredient": EntityType.DRUG,
    "lab_test_or_biomarker": EntityType.LAB_TEST,
    "procedure_or_intervention": EntityType.PROCEDURE,
    "anatomy_or_body_part": EntityType.ANATOMY,
    "hormone_enzyme_protein": EntityType.HORMONE,
    "pathogen_or_microbiology": EntityType.PATHOGEN,
    "device_or_technology": EntityType.DEVICE,
    "abbreviation_or_acronym": EntityType.ABBREVIATION,
    "general_medical_english": EntityType.UNKNOWN,
    "nutrition_or_supplement": EntityType.BIOMARKER,
    "chemical_or_biochemical": EntityType.DRUG,
    "unknown": EntityType.UNKNOWN,
}


class MedicalTermRecord(BaseModel):
    """Full provenance-tracked medical term record.

    Every column is required for traceability. Authoritative sources (ICD-10, RxNorm)
    get review_status=verified. LLM-generated terms get review_status=llm_candidate
    and llm_generated_candidate=True.
    """

    term_id: str = Field(
        ...,
        description="Unique term identifier, e.g. 'term_000001'. Format: term_<zero_padded_number>."
    )
    term_original: str = Field(
        ...,
        description="Original form as ingested from source (exact capitalization, punctuation)."
    )
    term_normalized: str = Field(
        ...,
        description="Normalized form for matching (lowercase, stripped, punctuation removed)."
    )
    entity_type: EntityType = Field(
        ...,
        description="Primary entity type from the 14-value FR2-04 taxonomy."
    )
    medical_domain: Optional[str] = Field(
        None,
        description="Medical domain, e.g. 'cardiology', 'endocrinology', 'neurology'."
    )
    source_name: TermSource = Field(
        ...,
        description="Named provenance source: icd10, rxnorm, openfda, vimedcss_seed, etc."
    )
    source_url: Optional[str] = Field(
        None,
        description="URL or API endpoint used to fetch this term. Null for manual seed lists."
    )
    source_license: Optional[str] = Field(
        None,
        description="License or access note for the source, e.g. 'NLM RxNorm — public domain'."
    )
    icd10_code: Optional[str] = Field(
        None,
        description="ICD-10 code if entity_type is disease. Null for non-disease terms."
    )
    rxnorm_rxcui: Optional[str] = Field(
        None,
        description="RxNorm Concept Unique Identifier (RxCUI) if entity_type is drug. Null otherwise."
    )
    is_code_switch_candidate: bool = Field(
        default=True,
        description="Whether this term can reasonably appear in EN/VI code-switching context."
    )
    review_status: ReviewStatus = Field(
        ...,
        description="Verification status: verified, llm_candidate, not_verified, needs_review."
    )
    llm_generated_candidate: bool = Field(
        default=False,
        description="True if this term was generated by LLM without external source verification."
    )
    fetched_at: str = Field(
        ...,
        description="ISO 8601 timestamp of ingestion, e.g. '2026-06-22T10:00:00Z'."
    )


class InventoryConfig(BaseModel):
    """Configuration for the medical term inventory build pipeline.

    Loaded from configs/term_inventory.yaml. CLI flags override these defaults.
    """

    icd10_backbone_path: str = Field(
        default="data/icd10/mock/icd10_dual_language.csv",
        description="Path to the Phase 6a ICD-10 bilingual CSV output (mock path)."
    )
    output_dir: str = Field(
        default="data/terms",
        description="Directory where medical_term_inventory.csv and related files are written."
    )
    log_dir: str = Field(
        default="logs",
        description="Directory for pipeline log files."
    )
    rxnorm_drug_list: List[str] = Field(
        default_factory=lambda: [
            "metformin", "insulin", "aspirin", "amoxicillin", "ibuprofen",
            "paracetamol", "atorvastatin", "losartan", "amlodipine", "omeprazole",
            "lisinopril", "simvastatin", "warfarin", "clopidogrel", "levothyroxine",
            "prednisone", "hba1c", "cholesterol", "triglyceride"
        ],
        description="Seed drug names to query against NLM RxNorm API."
    )
    abbreviation_list: List[str] = Field(
        default_factory=lambda: [
            "ECG", "MRI", "CT", "CBC", "EEG", "ICU", "CPR", "IV", "IM", "BP",
            "HR", "WBC", "RBC", "CRP", "HbA1c", "eGFR", "PSA", "HDL", "LDL",
            "COPD", "UTI", "GERD", "HIV", "AIDS"
        ],
        description="Manual abbreviation list — high-frequency medical abbreviations for EN/VI CS."
    )
    openfda_device_categories: List[str] = Field(
        default_factory=lambda: [
            "medical device",
            "diagnostic imaging device",
            "cardiac device"
        ],
        description="openFDA device category names to query."
    )
    confidence_threshold: float = Field(
        default=0.80,
        description="LLM classification confidence threshold. Terms below this require needs_review."
    )
    rxnorm_drug_list_mock: List[str] = Field(
        default_factory=lambda: ["metformin", "insulin", "aspirin"],
        description="Subset of rxnorm_drug_list used in --mock smoke test mode."
    )


class InventoryClassificationItem(BaseModel):
    """Classification result for a single term from the LLM.

    Used by MedicalTermClassifier to parse OpenAI structured output responses.
    """
    term_original: str = Field(
        ...,
        description="Original term as submitted to the LLM."
    )
    entity_type: EntityType = Field(
        ...,
        description="FR2-04 entity type: disease, drug, lab_test, procedure, anatomy, symptom, abbreviation, hormone, biomarker, pathogen, device, unit, dosage, unknown."
    )
    medical_domain: str = Field(
        ...,
        description="Medical domain: Medical Sciences, Pathology & Pathogens, Treatments, Nutrition, Diagnostics, or unknown."
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="LLM confidence score between 0.0 and 1.0."
    )
    needs_human_review: bool = Field(
        ...,
        description="True if confidence is below threshold or classification is ambiguous."
    )
    evidence: Optional[str] = Field(
        None,
        description="Brief reasoning or context for the classification."
    )
    uncertainty_reason: Optional[str] = Field(
        None,
        description="Explanation of why confidence is low or classification is uncertain."
    )


class InventoryClassificationBatchResponse(BaseModel):
    """OpenAI structured output schema for batch term classification.

    Returned by the LLM for a batch of terms sent to MedicalTermClassifier.
    """
    items: List[InventoryClassificationItem] = Field(
        default_factory=list,
        description="List of classification results, one per input term."
    )


InventoryClassificationBatchResponse.model_rebuild()