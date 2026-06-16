from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class EntityCategory(str, Enum):
    DRUG_OR_ACTIVE_INGREDIENT = "drug_or_active_ingredient"
    DISEASE_OR_CONDITION = "disease_or_condition"
    LAB_TEST_OR_BIOMARKER = "lab_test_or_biomarker"
    PROCEDURE_OR_INTERVENTION = "procedure_or_intervention"
    ANATOMY_OR_BODY_PART = "anatomy_or_body_part"
    HORMONE_ENZYME_PROTEIN = "hormone_enzyme_protein"
    PATHOGEN_OR_MICROBIOLOGY = "pathogen_or_microbiology"
    NUTRITION_OR_SUPPLEMENT = "nutrition_or_supplement"
    CHEMICAL_OR_BIOCHEMICAL = "chemical_or_biochemical"
    DEVICE_OR_TECHNOLOGY = "device_or_technology"
    GENERAL_MEDICAL_ENGLISH = "general_medical_english"
    ABBREVIATION_OR_ACRONYM = "abbreviation_or_acronym"
    UNKNOWN = "unknown"

class MedicalDomain(str, Enum):
    MEDICAL_SCIENCES = "Medical Sciences"
    PATHOLOGY_PATHOGENS = "Pathology & Pathogens"
    TREATMENTS = "Treatments"
    NUTRITION = "Nutrition"
    DIAGNOSTICS = "Diagnostics"
    UNKNOWN = "unknown"

class MedicalSpecialty(str, Enum):
    ENDOCRINOLOGY = "endocrinology"
    CARDIOLOGY = "cardiology"
    RESPIRATORY = "respiratory"
    INFECTIOUS_DISEASE = "infectious_disease"
    GASTROENTEROLOGY = "gastroenterology"
    NEUROLOGY = "neurology"
    ONCOLOGY = "oncology"
    OBSTETRICS_GYNECOLOGY = "obstetrics_gynecology"
    NEPHROLOGY = "nephrology"
    HEPATOLOGY = "hepatology"
    IMMUNOLOGY = "immunology"
    HEMATOLOGY = "hematology"
    NUTRITION = "nutrition"
    PHARMACOLOGY = "pharmacology"
    LABORATORY_MEDICINE = "laboratory_medicine"
    RADIOLOGY = "radiology"
    SURGERY = "surgery"
    GENERAL_MEDICINE = "general_medicine"
    UNKNOWN = "unknown"

class TermClassificationItem(BaseModel):
    normalized_term: str = Field(
        ...,
        description="The normalized term being classified, exactly matching the input term."
    )
    canonical_term: str = Field(
        ...,
        description="The canonical form of the term (e.g., standard capitalization or spelling)."
    )
    vietnamese_equivalent: str = Field(
        ...,
        description="The Vietnamese translation or equivalent of this medical term."
    )
    primary_entity_category: EntityCategory = Field(
        ...,
        description="The primary entity category of the term from the allowed list."
    )
    secondary_entity_categories: List[EntityCategory] = Field(
        default_factory=list,
        description="Zero or more secondary entity categories of the term from the allowed list."
    )
    primary_medical_domain: MedicalDomain = Field(
        ...,
        description="The primary Lớp 1 medical domain topic from the allowed list."
    )
    specialty: MedicalSpecialty = Field(
        ...,
        description="The primary Lớp 2 medical specialty from the allowed list."
    )
    candidate_domains: List[MedicalSpecialty] = Field(
        default_factory=list,
        description="Other candidate Lớp 2 medical specialties/domains."
    )
    is_abbreviation: bool = Field(
        ...,
        description="Whether this term is a medical abbreviation or acronym."
    )
    is_common_medical_term: bool = Field(
        ...,
        description="Whether this is a common term in medical language."
    )
    confidence: float = Field(
        ...,
        description="Confidence score for the classification (value between 0.0 and 1.0)."
    )
    evidence_from_context: str = Field(
        ...,
        description="Brief explanation of evidence found in the provided contexts."
    )
    needs_human_review: bool = Field(
        ...,
        description="True if the classification has high uncertainty, conflicts, or ambiguity."
    )
    uncertainty_reason: Optional[str] = Field(
        default=None,
        description="Detailing the reason for uncertainty or conflict if needs_human_review is True."
    )

class TermClassificationBatchResponse(BaseModel):
    taxonomy_version: str = Field(
        default="v1",
        description="Version of the taxonomy schema."
    )
    items: List[TermClassificationItem] = Field(
        ...,
        description="List of classified terms."
    )
