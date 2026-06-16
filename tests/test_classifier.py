import os
import json
import pandas as pd
import pytest
from src.llm.schemas import (
    TermClassificationItem,
    TermClassificationBatchResponse,
    EntityCategory,
    MedicalDomain,
    MedicalSpecialty
)
from src.llm.classifier import TermClassifier

def test_schemas_validation():
    # Test valid item parsing
    data = {
        "normalized_term": "metformin",
        "canonical_term": "Metformin",
        "vietnamese_equivalent": "metformin",
        "primary_entity_category": "drug_or_active_ingredient",
        "secondary_entity_categories": [],
        "primary_medical_domain": "Treatments",
        "specialty": "endocrinology",
        "candidate_domains": [],
        "is_abbreviation": False,
        "is_common_medical_term": True,
        "confidence": 0.95,
        "evidence_from_context": "Term appears in treatment context.",
        "needs_human_review": False
    }
    item = TermClassificationItem(**data)
    assert item.normalized_term == "metformin"
    assert item.primary_entity_category == EntityCategory.DRUG_OR_ACTIVE_INGREDIENT
    assert item.primary_medical_domain == MedicalDomain.TREATMENTS
    assert item.specialty == MedicalSpecialty.ENDOCRINOLOGY

    # Test invalid category validation
    invalid_data = data.copy()
    invalid_data["primary_entity_category"] = "invalid_category"
    with pytest.raises(ValueError):
        TermClassificationItem(**invalid_data)

@pytest.fixture
def mock_inventory_setup(tmp_path):
    # Create directory structure
    term_dir = tmp_path / "outputs" / "term_coverage"
    os.makedirs(term_dir, exist_ok=True)
    
    # Create a small mock inventory CSV file
    inv_data = [
        {
            "normalized_term": "metformin",
            "raw_forms": "Metformin;metformin",
            "occurrence_count": 5,
            "utterance_count": 5,
            "splits_present": "train;test;hard",
            "topics_present": "Treatments",
            "example_segment_ids": "seg1;seg2",
            "example_texts": "patient took metformin;diabetes treated with metformin",
            "entity_category": "unknown",
            "medical_domain": "unknown",
            "specialty": "unknown",
            "is_code_switch_term": True,
            "is_abbreviation": False,
            "is_common_term": True,
            "frequency_bucket": "medium",
            "classification_source": "none",
            "classification_confidence": 0.0,
            "needs_human_review": False,
            "notes": ""
        },
        {
            "normalized_term": "hba1c",
            "raw_forms": "HbA1c;HBA1C",
            "occurrence_count": 2,
            "utterance_count": 2,
            "splits_present": "test;hard",
            "topics_present": "Diagnostics",
            "example_segment_ids": "seg3",
            "example_texts": "check HbA1c levels",
            "entity_category": "unknown",
            "medical_domain": "unknown",
            "specialty": "unknown",
            "is_code_switch_term": True,
            "is_abbreviation": True,
            "is_common_term": False,
            "frequency_bucket": "rare",
            "classification_source": "none",
            "classification_confidence": 0.0,
            "needs_human_review": False,
            "notes": ""
        }
    ]
    inv_df = pd.DataFrame(inv_data)
    inv_csv_path = term_dir / "cs_terms_inventory.csv"
    inv_df.to_csv(inv_csv_path, index=False)
    
    dataset_config = {
        "local_raw_dir": str(tmp_path),
        "expected_fields": {},
        "splits": ["train", "test", "hard"]
    }
    taxonomy_config = {
        "frequency_buckets": {
            "singleton": [1, 1],
            "rare": [2, 4],
            "medium": [5, 19],
            "common": [20, None]
        },
        "confidence_threshold_review": 0.80
    }
    llm_config = {
        "enabled": True,
        "provider": "openai",
        "model": "gpt-5-mini",
        "structured_output": True,
        "batch_size": 2,
        "max_retries": 1
    }
    return str(tmp_path), dataset_config, taxonomy_config, llm_config

def test_term_classifier_mock_run(mock_inventory_setup):
    tmp_path_str, dataset_config, taxonomy_config, llm_config = mock_inventory_setup
    
    classifier = TermClassifier(dataset_config, taxonomy_config, llm_config)
    # Patch output paths and output directory to redirect to tmp_path
    classifier.output_dir = os.path.join(tmp_path_str, "outputs", "term_coverage")
    classifier.inventory_path = os.path.join(classifier.output_dir, "cs_terms_inventory.csv")
    classifier.audit_log_path = os.path.join(classifier.output_dir, "llm_classification_audit.jsonl")
    
    # Run in mock classification mode
    stats = classifier.classify(mock=True)
    
    assert stats["total_classified"] == 2
    
    # Check updated inventory CSV
    inv_df = pd.read_csv(classifier.inventory_path)
    assert len(inv_df) == 2
    
    # Validate classification columns updated from mock rules
    metformin_row = inv_df[inv_df["normalized_term"] == "metformin"].iloc[0]
    assert metformin_row["entity_category"] == "drug_or_active_ingredient"
    assert metformin_row["medical_domain"] == "Treatments"
    assert metformin_row["specialty"] == "endocrinology"
    assert metformin_row["classification_source"] == "mock"
    assert metformin_row["classification_confidence"] > 0.80
    assert bool(metformin_row["needs_human_review"]) is False
    assert metformin_row["vietnamese_equivalent"] == "metformin"
    
    hba1c_row = inv_df[inv_df["normalized_term"] == "hba1c"].iloc[0]
    assert hba1c_row["entity_category"] == "lab_test_or_biomarker"
    assert hba1c_row["medical_domain"] == "Diagnostics"
    assert hba1c_row["specialty"] == "endocrinology"
    assert bool(hba1c_row["is_abbreviation"]) is True
    
    # Verify generated grouping/filtered files
    assert os.path.exists(os.path.join(classifier.output_dir, "cs_terms_by_entity_category.csv"))
    assert os.path.exists(os.path.join(classifier.output_dir, "cs_terms_by_domain.csv"))
    assert os.path.exists(os.path.join(classifier.output_dir, "term_taxonomy_summary.md"))
    assert os.path.exists(os.path.join(classifier.output_dir, "rare_terms.csv"))
    
    # Verify audit log exists
    assert os.path.exists(classifier.audit_log_path)
    with open(classifier.audit_log_path, "r", encoding="utf-8") as f:
        log_line = json.loads(f.readline())
        assert log_line["request"]["task"] == "mock_classification"
        assert log_line["response"]["status"] == "success"
        
    # Verify summary md content
    with open(os.path.join(classifier.output_dir, "term_taxonomy_summary.md"), "r", encoding="utf-8") as f:
        summary_content = f.read()
        assert "Tổng số thuật ngữ độc nhất đã phân loại" in summary_content
        assert "Phân phối theo Entity Category" in summary_content
        assert "Phân phối theo Lớp 2 (Specialty)" in summary_content
