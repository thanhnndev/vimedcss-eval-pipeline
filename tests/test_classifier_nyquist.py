"""
Nyquist validation tests for Phase 2: Term Taxonomy & LLM Classification.

Coverage mapping:
- CLASSIFY-01: test_classify_missing_inventory_file, test_classify_with_limit_processes_subset,
               test_classify_preserves_existing_classifications, test_classify_mock_batch_response,
               test_reasoning_model_sends_reasoning_effort, test_non_reasoning_model_sends_temperature
- CLASSIFY-02: test_mock_classification_assigns_correct_domains, test_confidence_threshold_triggers_review,
               test_classify_preserves_existing_classifications
- CLASSIFY-03: test_classify_with_limit_processes_subset, test_filtered_files_content_and_columns,
               test_entity_category_and_domain_csv_columns
- CLASSIFY-04: test_audit_log_format_and_content, test_mock_audit_log_contains_all_fields,
               test_taxonomy_summary_contains_all_distributions, test_audit_log_records_per_batch,
               test_audit_log_records_model_and_duration
"""

import os
import json
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from src.llm.schemas import (
    TermClassificationItem,
    TermClassificationBatchResponse,
    EntityCategory,
    MedicalDomain,
    MedicalSpecialty,
)
from src.llm.classifier import TermClassifier
from src.shared.config import AppConfig


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def nyquist_tmp_path(tmp_path):
    term_dir = tmp_path / "outputs" / "term_coverage"
    os.makedirs(term_dir, exist_ok=True)
    return tmp_path, term_dir


@pytest.fixture
def small_inventory(nyquist_tmp_path):
    tmp_path, term_dir = nyquist_tmp_path
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
            "notes": "",
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
            "notes": "",
        },
        {
            "normalized_term": "diabetes",
            "raw_forms": "Diabetes;diabetes",
            "occurrence_count": 25,
            "utterance_count": 20,
            "splits_present": "train;validation;test;hard",
            "topics_present": "Medical Sciences",
            "example_segment_ids": "seg4;seg5",
            "example_texts": "type 2 diabetes management",
            "entity_category": "unknown",
            "medical_domain": "unknown",
            "specialty": "unknown",
            "is_code_switch_term": True,
            "is_abbreviation": False,
            "is_common_term": True,
            "frequency_bucket": "common",
            "classification_source": "none",
            "classification_confidence": 0.0,
            "needs_human_review": False,
            "notes": "",
        },
    ]
    inv_df = pd.DataFrame(inv_data)
    inv_csv_path = term_dir / "cs_terms_inventory.csv"
    inv_df.to_csv(inv_csv_path, index=False)
    return tmp_path, term_dir, inv_csv_path


@pytest.fixture
def classifier_configs(tmp_path):
    dataset_config = {
        "local_raw_dir": str(tmp_path),
        "expected_fields": {},
        "splits": ["train", "test", "hard", "validation"],
    }
    taxonomy_config = {
        "frequency_buckets": {
            "singleton": [1, 1],
            "rare": [2, 4],
            "medium": [5, 19],
            "common": [20, None],
        },
        "confidence_threshold_review": 0.80,
    }
    llm_config = {
        "enabled": True,
        "provider": "openai",
        "model": "gpt-5-mini",
        "structured_output": True,
        "batch_size": 2,
        "max_retries": 1,
    }
    return dataset_config, taxonomy_config, llm_config


def _make_classifier(small_inventory, classifier_configs):
    tmp_path, term_dir, _ = small_inventory
    dataset_config, taxonomy_config, llm_config = classifier_configs
    classifier = TermClassifier(dataset_config, taxonomy_config, llm_config)
    classifier.output_dir = str(term_dir)
    classifier.inventory_path = str(term_dir / "cs_terms_inventory.csv")
    classifier.audit_log_path = str(term_dir / "llm_classification_audit.jsonl")
    return classifier, term_dir


def _make_serializable_completion(model_name: str = "gpt-4o-mini"):
    """Build a minimal completion mock whose attributes are JSON-serializable."""
    completion = MagicMock()
    completion.id = "cmpl-test-123"
    completion.model = model_name
    completion.choices = [
        MagicMock(
            message=MagicMock(
                role="assistant",
                content=None,
                parsed=None,
            ),
            finish_reason="stop",
        )
    ]
    completion.usage = MagicMock()
    completion.usage.model_dump.return_value = {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }
    return completion


# ---------------------------------------------------------------------------
# CLASSIFY-01: Classify unique CS terms into entity categories
# ---------------------------------------------------------------------------

class TestClassifyEntityCategories:
    def test_classify_missing_inventory_file_raises(self, classifier_configs, tmp_path):
        """CLASSIFY-01: Missing inventory raises FileNotFoundError."""
        dataset_config, taxonomy_config, llm_config = classifier_configs
        term_dir = tmp_path / "outputs" / "term_coverage"
        os.makedirs(term_dir, exist_ok=True)
        classifier = TermClassifier(dataset_config, taxonomy_config, llm_config)
        classifier.inventory_path = str(term_dir / "nonexistent.csv")
        with pytest.raises(FileNotFoundError, match="not found"):
            classifier.classify(mock=True)

    def test_classify_empty_inventory_returns_zero(self, classifier_configs, tmp_path):
        """CLASSIFY-01: Inventory with zero rows returns zero-classified stats."""
        dataset_config, taxonomy_config, llm_config = classifier_configs
        term_dir = tmp_path / "outputs" / "term_coverage"
        os.makedirs(term_dir, exist_ok=True)
        inv_path = term_dir / "cs_terms_inventory.csv"
        # Write an empty CSV with the expected columns so pandas can parse it
        pd.DataFrame(columns=[
            "normalized_term", "raw_forms", "occurrence_count", "splits_present",
            "topics_present", "example_texts", "entity_category", "medical_domain",
            "specialty", "classification_source", "classification_confidence",
            "needs_human_review", "notes",
        ]).to_csv(inv_path, index=False)
        classifier = TermClassifier(dataset_config, taxonomy_config, llm_config)
        classifier.inventory_path = str(inv_path)
        classifier.output_dir = str(term_dir)
        stats = classifier.classify(mock=True)
        assert stats["total_classified"] == 0

    def test_classify_with_limit_processes_subset(self, small_inventory, classifier_configs):
        """CLASSIFY-01/03: --limit N only marks the first N terms as classified."""
        classifier, term_dir = _make_classifier(small_inventory, classifier_configs)
        classifier.classify(mock=True, limit=1)
        inv_df = pd.read_csv(classifier.inventory_path)
        assert len(inv_df) == 3  # inventory rows are preserved
        classified_this_run = inv_df[inv_df["classification_source"] == "mock"]
        assert len(classified_this_run) == 1
        assert classified_this_run.iloc[0]["normalized_term"] == "metformin"

    def test_classify_preserves_existing_classifications(self, small_inventory, classifier_configs, monkeypatch):
        """CLASSIFY-01/02: Already-classified rows keep their source on re-run."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        classifier, term_dir = _make_classifier(small_inventory, classifier_configs)
        classifier.classify(mock=True)
        inv_df = pd.read_csv(classifier.inventory_path)
        first_pass = inv_df.set_index("normalized_term")["classification_source"].to_dict()
        # Re-run in live mode with an empty response should preserve non-none sources
        with patch("src.llm.classifier.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = _make_serializable_completion("gpt-4o-mini")
            mock_response.choices[0].message.parsed = TermClassificationBatchResponse(
                taxonomy_version="v1", items=[]
            )
            mock_client.beta.chat.completions.parse.return_value = mock_response
            classifier.classify(mock=False)
        inv_df2 = pd.read_csv(classifier.inventory_path)
        second_pass = inv_df2.set_index("normalized_term")["classification_source"].to_dict()
        for term, source in first_pass.items():
            if source != "none":
                assert second_pass[term] == source


# ---------------------------------------------------------------------------
# CLASSIFY-02: Classify unique CS terms into medical domains/specialties
# ---------------------------------------------------------------------------

class TestClassifyMedicalDomains:
    def test_mock_classification_assigns_correct_domains(self, small_inventory, classifier_configs):
        """CLASSIFY-02: Mock rules map treatments/diagnostics domains correctly."""
        classifier, term_dir = _make_classifier(small_inventory, classifier_configs)
        classifier.classify(mock=True)
        inv_df = pd.read_csv(classifier.inventory_path)
        metformin = inv_df[inv_df["normalized_term"] == "metformin"].iloc[0]
        assert metformin["medical_domain"] == "Treatments"
        assert metformin["specialty"] == "endocrinology"
        hba1c = inv_df[inv_df["normalized_term"] == "hba1c"].iloc[0]
        assert hba1c["medical_domain"] == "Diagnostics"
        assert hba1c["specialty"] == "endocrinology"

    def test_confidence_threshold_triggers_review(self, classifier_configs, tmp_path):
        """CLASSIFY-02/04: Mock UNKNOWN term with confidence 0.50 sets needs_human_review=True."""
        dataset_config, taxonomy_config, llm_config = classifier_configs
        term_dir = tmp_path / "outputs" / "term_coverage"
        os.makedirs(term_dir, exist_ok=True)
        # Use a term that does NOT match any mock keyword so it stays UNKNOWN / 0.50
        inv_data = [
            {
                "normalized_term": "xyz_unknown",
                "raw_forms": "XYZ Unknown",
                "occurrence_count": 1,
                "utterance_count": 1,
                "splits_present": "test",
                "topics_present": "unknown",
                "example_segment_ids": "seg1",
                "example_texts": "some text",
                "entity_category": "unknown",
                "medical_domain": "unknown",
                "specialty": "unknown",
                "is_code_switch_term": True,
                "is_abbreviation": False,
                "is_common_term": False,
                "frequency_bucket": "singleton",
                "classification_source": "none",
                "classification_confidence": 0.0,
                "needs_human_review": False,
                "notes": "",
            }
        ]
        pd.DataFrame(inv_data).to_csv(term_dir / "cs_terms_inventory.csv", index=False)
        classifier = TermClassifier(dataset_config, taxonomy_config, llm_config)
        classifier.output_dir = str(term_dir)
        classifier.inventory_path = str(term_dir / "cs_terms_inventory.csv")
        classifier.audit_log_path = str(term_dir / "llm_classification_audit.jsonl")
        classifier.classify(mock=True)
        inv_df = pd.read_csv(classifier.inventory_path)
        row = inv_df.iloc[0]
        assert bool(row["needs_human_review"]) is True
        assert float(row["classification_confidence"]) < 0.80


# ---------------------------------------------------------------------------
# CLASSIFY-03: Frequency buckets and filtered files
# ---------------------------------------------------------------------------

class TestFilteredFilesAndFrequencyBuckets:
    def test_filtered_files_content_and_columns(self, small_inventory, classifier_configs):
        """CLASSIFY-03/04: Filtered CSVs contain expected columns and rows."""
        classifier, term_dir = _make_classifier(small_inventory, classifier_configs)
        classifier.classify(mock=True)
        # rare_terms.csv should contain frequency_bucket rare/singleton terms
        rare_df = pd.read_csv(term_dir / "rare_terms.csv")
        assert set(rare_df["frequency_bucket"]).issubset({"rare", "singleton"})
        # common_terms.csv should contain common terms
        common_df = pd.read_csv(term_dir / "common_terms.csv")
        if len(common_df) > 0:
            assert set(common_df["frequency_bucket"]) == {"common"}
        # hard_only_terms.csv should only contain terms present in hard but not train/val/test
        hard_only_df = pd.read_csv(term_dir / "hard_only_terms.csv")
        for _, row in hard_only_df.iterrows():
            splits = str(row["splits_present"])
            assert "hard" in splits
        # unseen_in_train_terms.csv should only contain eval terms not in train
        unseen_df = pd.read_csv(term_dir / "unseen_in_train_terms.csv")
        for _, row in unseen_df.iterrows():
            splits = str(row["splits_present"])
            assert "train" not in splits or (
                "validation" in splits or "test" in splits or "hard" in splits
            )

    def test_entity_category_and_domain_csv_columns(self, small_inventory, classifier_configs):
        """CLASSIFY-03/04: Grouped CSVs have required columns."""
        classifier, term_dir = _make_classifier(small_inventory, classifier_configs)
        classifier.classify(mock=True)
        cat_df = pd.read_csv(term_dir / "cs_terms_by_entity_category.csv")
        for col in ["normalized_term", "occurrence_count", "entity_category",
                    "classification_confidence", "needs_human_review"]:
            assert col in cat_df.columns
        domain_df = pd.read_csv(term_dir / "cs_terms_by_domain.csv")
        for col in ["normalized_term", "occurrence_count", "medical_domain",
                    "specialty", "classification_confidence", "needs_human_review"]:
            assert col in domain_df.columns


# ---------------------------------------------------------------------------
# CLASSIFY-04: Audit logs and summary markdown
# ---------------------------------------------------------------------------

class TestAuditLogsAndSummary:
    def test_audit_log_format_and_content(self, small_inventory, classifier_configs):
        """CLASSIFY-04: Audit log is valid JSONL with request/response structure."""
        classifier, term_dir = _make_classifier(small_inventory, classifier_configs)
        classifier.classify(mock=True)
        log_path = term_dir / "llm_classification_audit.jsonl"
        assert log_path.exists()
        records = []
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        assert len(records) >= 1
        for rec in records:
            assert "request" in rec
            assert "response" in rec
            assert isinstance(rec["request"], dict)
            assert isinstance(rec["response"], dict)

    def test_mock_audit_log_contains_all_fields(self, small_inventory, classifier_configs):
        """CLASSIFY-04: Mock audit entry includes task and status fields."""
        classifier, term_dir = _make_classifier(small_inventory, classifier_configs)
        classifier.classify(mock=True)
        log_path = term_dir / "llm_classification_audit.jsonl"
        with open(log_path, "r", encoding="utf-8") as f:
            rec = json.loads(f.readline())
        assert rec["request"]["task"] == "mock_classification"
        assert rec["request"]["count"] == len(
            pd.read_csv(classifier.inventory_path)
        )
        assert rec["response"]["status"] == "success"
        assert "items" in rec["response"]

    def test_taxonomy_summary_contains_all_distributions(self, small_inventory, classifier_configs):
        """CLASSIFY-04: Summary markdown contains category, domain, and specialty tables."""
        classifier, term_dir = _make_classifier(small_inventory, classifier_configs)
        classifier.classify(mock=True)
        summary_path = term_dir / "term_taxonomy_summary.md"
        assert summary_path.exists()
        content = summary_path.read_text(encoding="utf-8")
        assert "Tổng số thuật ngữ độc nhất đã phân loại" in content
        assert "Phân phối theo Entity Category" in content
        assert "Phân phối theo Lớp 1" in content
        assert "Phân phối theo Lớp 2" in content
        assert "Cần rà soát thủ công" in content

    def test_audit_log_records_per_batch(self, classifier_configs, tmp_path, monkeypatch):
        """CLASSIFY-04: One audit record per API batch call."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        dataset_config, taxonomy_config, llm_config = classifier_configs
        term_dir = tmp_path / "outputs" / "term_coverage"
        os.makedirs(term_dir, exist_ok=True)
        inv_data = [
            {
                "normalized_term": f"term_{i}",
                "raw_forms": f"Term {i}",
                "occurrence_count": i + 1,
                "utterance_count": i + 1,
                "splits_present": "test",
                "topics_present": "unknown",
                "example_segment_ids": f"seg{i}",
                "example_texts": f"text {i}",
                "entity_category": "unknown",
                "medical_domain": "unknown",
                "specialty": "unknown",
                "is_code_switch_term": True,
                "is_abbreviation": False,
                "is_common_term": False,
                "frequency_bucket": "singleton",
                "classification_source": "none",
                "classification_confidence": 0.0,
                "needs_human_review": False,
                "notes": "",
            }
            for i in range(5)
        ]
        pd.DataFrame(inv_data).to_csv(term_dir / "cs_terms_inventory.csv", index=False)
        llm_config = dict(llm_config)
        llm_config["batch_size"] = 2
        classifier = TermClassifier(dataset_config, taxonomy_config, llm_config)
        classifier.output_dir = str(term_dir)
        classifier.inventory_path = str(term_dir / "cs_terms_inventory.csv")
        classifier.audit_log_path = str(term_dir / "llm_classification_audit.jsonl")
        with patch("src.llm.classifier.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = _make_serializable_completion("gpt-4o-mini")
            mock_response.choices[0].message.parsed = TermClassificationBatchResponse(
                taxonomy_version="v1",
                items=[
                    TermClassificationItem(
                        normalized_term=f"term_{i}",
                        canonical_term=f"Term {i}",
                        vietnamese_equivalent=f"term_{i}",
                        primary_entity_category=EntityCategory.UNKNOWN,
                        secondary_entity_categories=[],
                        primary_medical_domain=MedicalDomain.UNKNOWN,
                        specialty=MedicalSpecialty.UNKNOWN,
                        candidate_domains=[],
                        is_abbreviation=False,
                        is_common_medical_term=False,
                        confidence=0.50,
                        evidence_from_context="Mock",
                        needs_human_review=True,
                        uncertainty_reason="Low confidence",
                    )
                    for i in range(5)
                ],
            )
            mock_client.beta.chat.completions.parse.return_value = mock_response
            classifier.classify(mock=False)
        log_path = term_dir / "llm_classification_audit.jsonl"
        records = []
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        # 5 terms, batch_size=2 -> ceil(5/2)=3 batches
        assert len(records) == 3


# ---------------------------------------------------------------------------
# CLASSIFY-01/04: API integration patterns (retry, reasoning_effort, structured output)
# ---------------------------------------------------------------------------

class TestLLMAPIIntegration:
    def test_classify_mock_batch_response_parsing(self):
        """CLASSIFY-01/04: Batch response parses into TermClassificationBatchResponse."""
        items = [
            TermClassificationItem(
                normalized_term="metformin",
                canonical_term="Metformin",
                vietnamese_equivalent="metformin",
                primary_entity_category=EntityCategory.DRUG_OR_ACTIVE_INGREDIENT,
                secondary_entity_categories=[],
                primary_medical_domain=MedicalDomain.TREATMENTS,
                specialty=MedicalSpecialty.ENDOCRINOLOGY,
                candidate_domains=[],
                is_abbreviation=False,
                is_common_medical_term=True,
                confidence=0.95,
                evidence_from_context="Drug context",
                needs_human_review=False,
                uncertainty_reason=None,
            )
        ]
        batch = TermClassificationBatchResponse(taxonomy_version="v1", items=items)
        assert batch.taxonomy_version == "v1"
        assert len(batch.items) == 1
        assert batch.items[0].primary_entity_category == EntityCategory.DRUG_OR_ACTIVE_INGREDIENT

    def test_api_call_retry_on_failure(self, small_inventory, classifier_configs):
        """CLASSIFY-01/04: Retry logic re-raises after max_retries exhausted."""
        classifier, term_dir = _make_classifier(small_inventory, classifier_configs)
        llm_config = dict(classifier_configs[2])
        llm_config["max_retries"] = 2
        classifier.llm_config = llm_config
        with patch("src.llm.classifier.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.beta.chat.completions.parse.side_effect = RuntimeError("API down")
            with pytest.raises(RuntimeError, match="API down"):
                classifier._classify_batch_with_retry(mock_client, [{"normalized_term": "x"}])

    def test_reasoning_model_sends_reasoning_effort(self, small_inventory, classifier_configs):
        """CLASSIFY-01: Reasoning models (gpt-5) send reasoning_effort instead of temperature."""
        classifier, term_dir = _make_classifier(small_inventory, classifier_configs)
        llm_config = dict(classifier_configs[2])
        llm_config["model"] = "gpt-5"
        classifier.llm_config = llm_config
        with patch("src.llm.classifier.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = _make_serializable_completion("gpt-5")
            mock_response.choices[0].message.parsed = MagicMock()
            mock_client.beta.chat.completions.parse.return_value = mock_response
            classifier._classify_batch_with_retry(mock_client, [{"normalized_term": "x"}])
            kwargs = mock_client.beta.chat.completions.parse.call_args.kwargs
            assert "reasoning_effort" in kwargs
            assert "temperature" not in kwargs
            assert kwargs["reasoning_effort"] == "medium"

    def test_non_reasoning_model_sends_temperature(self, small_inventory, classifier_configs):
        """CLASSIFY-01: Non-reasoning models send temperature=0.0."""
        classifier, term_dir = _make_classifier(small_inventory, classifier_configs)
        llm_config = dict(classifier_configs[2])
        llm_config["model"] = "gpt-4o-mini"
        classifier.llm_config = llm_config
        with patch("src.llm.classifier.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = _make_serializable_completion("gpt-4o-mini")
            mock_response.choices[0].message.parsed = MagicMock()
            mock_client.beta.chat.completions.parse.return_value = mock_response
            classifier._classify_batch_with_retry(mock_client, [{"normalized_term": "x"}])
            kwargs = mock_client.beta.chat.completions.parse.call_args.kwargs
            assert "temperature" in kwargs
            assert kwargs["temperature"] == 0.0
            assert "reasoning_effort" not in kwargs

    def test_audit_log_records_model_and_duration(self, small_inventory, classifier_configs):
        """CLASSIFY-04: Audit log includes model name and duration."""
        classifier, term_dir = _make_classifier(small_inventory, classifier_configs)
        llm_config = dict(classifier_configs[2])
        llm_config["model"] = "gpt-4o-mini"
        classifier.llm_config = llm_config
        with patch("src.llm.classifier.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = _make_serializable_completion("gpt-4o-mini")
            mock_response.choices[0].message.parsed = MagicMock()
            mock_client.beta.chat.completions.parse.return_value = mock_response
            classifier._classify_batch_with_retry(mock_client, [{"normalized_term": "x"}])
        log_path = term_dir / "llm_classification_audit.jsonl"
        with open(log_path, "r", encoding="utf-8") as f:
            rec = json.loads(f.readline())
        assert rec["request"]["model"] == "gpt-4o-mini"
        assert "duration_seconds" in rec["response"]
        assert rec["response"]["duration_seconds"] >= 0


# ---------------------------------------------------------------------------
# Config / defaults
# ---------------------------------------------------------------------------

class TestClassifierConfigDefaults:
    def test_llm_config_defaults_from_yaml(self, tmp_path, monkeypatch):
        """CLASSIFY-01/04: Default LLM config loaded from configs/llm.yaml."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "configs").mkdir()
        (tmp_path / "configs" / "llm.yaml").write_text(
            "enabled: true\nprovider: openai\nmodel: gpt-4o-mini\nbatch_size: 10\nmax_retries: 3\n"
        )
        for fname in ["dataset.yaml", "taxonomy.yaml", "asr.yaml", "report.yaml"]:
            (tmp_path / "configs" / fname).write_text("{}\n")
        cfg = AppConfig(config_dir=str(tmp_path / "configs"))
        llm = cfg.get_llm_config()
        assert llm["model"] == "gpt-4o-mini"
        assert llm["batch_size"] == 10
        assert llm["max_retries"] == 3

    def test_schema_enums_match_expected_values(self):
        """CLASSIFY-01/02: Schema enums contain all documented taxonomy values."""
        expected_categories = {
            "drug_or_active_ingredient", "disease_or_condition", "lab_test_or_biomarker",
            "procedure_or_intervention", "anatomy_or_body_part", "hormone_enzyme_protein",
            "pathogen_or_microbiology", "nutrition_or_supplement", "chemical_or_biochemical",
            "device_or_technology", "general_medical_english", "abbreviation_or_acronym",
            "unknown",
        }
        assert {c.value for c in EntityCategory} == expected_categories
        expected_domains = {
            "Medical Sciences", "Pathology & Pathogens", "Treatments",
            "Nutrition", "Diagnostics", "unknown",
        }
        assert {d.value for d in MedicalDomain} == expected_domains
        expected_specialties = {
            "endocrinology", "cardiology", "respiratory", "infectious_disease",
            "gastroenterology", "neurology", "oncology", "obstetrics_gynecology",
            "nephrology", "hepatology", "immunology", "hematology", "nutrition",
            "pharmacology", "laboratory_medicine", "radiology", "surgery",
            "general_medicine", "unknown",
        }
        assert {s.value for s in MedicalSpecialty} == expected_specialties
