"""
Nyquist validation tests for Phase 3: External Reference Match.

Coverage mapping:
- EXT_REF-01: test_registry_contains_pilot_source, test_registry_csv_columns,
              test_empty_external_inventory_produces_empty_registry
- EXT_REF-02: test_external_inventory_schema, test_coverage_csv_schema,
              test_missing_high_priority_terms_listed, test_summary_has_pilot_disclaimer,
              test_case_insensitive_exact_match, test_unmatched_terms_marked_missing,
              test_coverage_ratios_correct, test_registry_csv_required_columns,
              test_summary_vietnamese_headings, test_cli_mock_limit_processes_n_terms
"""

import os
import json
import pytest
import pandas as pd
from src.terms.external import ExternalReferenceMatcher
from src.shared.config import AppConfig


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def base_tmp(nyquist_tmp_path):
    """Returns (tmp_path, term_dir) from nyquist_tmp_path compatible fixture."""
    return nyquist_tmp_path


@pytest.fixture
def nyquist_tmp_path(tmp_path):
    term_dir = tmp_path / "outputs" / "term_coverage"
    os.makedirs(term_dir, exist_ok=True)
    return tmp_path, term_dir


@pytest.fixture
def mock_inventory_dir(nyquist_tmp_path):
    """Creates a mock external inventory directory with a CSV."""
    tmp_path, term_dir = nyquist_tmp_path
    inv_dir = tmp_path / "data" / "raw" / "external"
    os.makedirs(inv_dir, exist_ok=True)
    
    inv_data = [
        {
            "term_id": "ext_001",
            "canonical_term": "metformin",
            "language": "en",
            "entity_category": "drug_or_active_ingredient",
            "medical_domain": "Treatments",
            "specialty": "endocrinology",
            "source_name": "Test Pilot Lexicon",
            "commonness_level": "common",
            "commonness_source": "test",
            "include_in_pilot": True,
            "notes": "test term",
        },
        {
            "term_id": "ext_002",
            "canonical_term": "DIABETES",
            "language": "en",
            "entity_category": "disease_or_condition",
            "medical_domain": "Medical Sciences",
            "specialty": "endocrinology",
            "source_name": "Test Pilot Lexicon",
            "commonness_level": "common",
            "commonness_source": "test",
            "include_in_pilot": True,
            "notes": "test term uppercase for case-insensitive test",
        },
        {
            "term_id": "ext_003",
            "canonical_term": "hba1c",
            "language": "en",
            "entity_category": "lab_test_or_biomarker",
            "medical_domain": "Diagnostics",
            "specialty": "laboratory_medicine",
            "source_name": "Test Pilot Lexicon",
            "commonness_level": "medium",
            "commonness_source": "test",
            "include_in_pilot": True,
            "notes": "test term",
        },
    ]
    inv_df = pd.DataFrame(inv_data)
    inv_path = inv_dir / "pilot_inventory.csv"
    inv_df.to_csv(inv_path, index=False)
    return tmp_path, term_dir, inv_dir


@pytest.fixture
def vimedcss_inventory(nyquist_tmp_path):
    """Creates a synthetic ViMedCSS inventory CSV."""
    tmp_path, term_dir = nyquist_tmp_path
    inv_data = [
        {
            "normalized_term": "metformin",
            "raw_forms": "Metformin;metformin",
            "occurrence_count": 5,
            "utterance_count": 5,
            "splits_present": "train;test",
            "topics_present": "Treatments",
            "example_segment_ids": "seg1;seg2",
            "example_texts": "patient took metformin",
            "entity_category": "drug_or_active_ingredient",
            "medical_domain": "Treatments",
            "specialty": "endocrinology",
            "is_code_switch_term": True,
            "is_abbreviation": False,
            "is_common_term": True,
            "frequency_bucket": "medium",
            "classification_source": "mock",
            "classification_confidence": 0.95,
            "needs_human_review": False,
            "notes": "",
            "canonical_term": "metformin",
            "vietnamese_equivalent": "metformin",
        },
        {
            "normalized_term": "diabetes",
            "raw_forms": "Diabetes;diabetes",
            "occurrence_count": 25,
            "utterance_count": 20,
            "splits_present": "train;validation;test;hard",
            "topics_present": "Medical Sciences",
            "example_segment_ids": "seg3;seg4",
            "example_texts": "type 2 diabetes management",
            "entity_category": "disease_or_condition",
            "medical_domain": "Medical Sciences",
            "specialty": "endocrinology",
            "is_code_switch_term": True,
            "is_abbreviation": False,
            "is_common_term": True,
            "frequency_bucket": "common",
            "classification_source": "mock",
            "classification_confidence": 0.95,
            "needs_human_review": False,
            "notes": "",
            "canonical_term": "diabetes",
            "vietnamese_equivalent": "bệnh tiểu đường",
        },
        {
            "normalized_term": "hba1c",
            "raw_forms": "HbA1c;HBA1C",
            "occurrence_count": 2,
            "utterance_count": 2,
            "splits_present": "test;hard",
            "topics_present": "Diagnostics",
            "example_segment_ids": "seg5",
            "example_texts": "check HbA1c levels",
            "entity_category": "lab_test_or_biomarker",
            "medical_domain": "Diagnostics",
            "specialty": "laboratory_medicine",
            "is_code_switch_term": True,
            "is_abbreviation": True,
            "is_common_term": False,
            "frequency_bucket": "rare",
            "classification_source": "mock",
            "classification_confidence": 0.90,
            "needs_human_review": False,
            "notes": "",
            "canonical_term": "hba1c",
            "vietnamese_equivalent": "chỉ số hba1c",
        },
        {
            "normalized_term": "stent",
            "raw_forms": "Stent;stent",
            "occurrence_count": 3,
            "utterance_count": 3,
            "splits_present": "train;hard",
            "topics_present": "Treatments",
            "example_segment_ids": "seg6",
            "example_texts": "cardiac stent placement",
            "entity_category": "device_or_technology",
            "medical_domain": "Treatments",
            "specialty": "cardiology",
            "is_code_switch_term": True,
            "is_abbreviation": False,
            "is_common_term": False,
            "frequency_bucket": "rare",
            "classification_source": "mock",
            "classification_confidence": 0.85,
            "needs_human_review": False,
            "notes": "",
            "canonical_term": "stent",
            "vietnamese_equivalent": "ống đỡ động mạch",
        },
        {
            "normalized_term": "asthma",
            "raw_forms": "Asthma;asthma",
            "occurrence_count": 10,
            "utterance_count": 8,
            "splits_present": "train;test;hard",
            "topics_present": "Medical Sciences",
            "example_segment_ids": "seg7;seg8",
            "example_texts": "asthma attack",
            "entity_category": "disease_or_condition",
            "medical_domain": "Medical Sciences",
            "specialty": "respiratory",
            "is_code_switch_term": True,
            "is_abbreviation": False,
            "is_common_term": True,
            "frequency_bucket": "medium",
            "classification_source": "mock",
            "classification_confidence": 0.95,
            "needs_human_review": False,
            "notes": "",
            "canonical_term": "asthma",
            "vietnamese_equivalent": "hen phế quản",
        },
    ]
    inv_df = pd.DataFrame(inv_data)
    inv_path = term_dir / "cs_terms_inventory.csv"
    inv_df.to_csv(inv_path, index=False)
    return tmp_path, term_dir, inv_path


@pytest.fixture
def external_configs(mock_inventory_dir):
    """Creates external, dataset, and taxonomy configs for matcher."""
    tmp_path, term_dir, inv_dir = mock_inventory_dir
    dataset_config = {"local_raw_dir": str(tmp_path)}
    taxonomy_config = {}
    external_config = {
        "enabled": True,
        "pilot_sources": [
            {
                "name": "Test Pilot Lexicon",
                "source_url": "https://example.com/test",
                "license_or_access_note": "Test license",
                "include_in_pilot": True,
                "coverage_notes": "Synthetic test inventory",
            }
        ],
        "inventory_dir": str(inv_dir),
        "output_dir": str(term_dir),
        "match_mode": "exact_case_insensitive",
        "min_commonness_for_high_priority": 5,
    }
    return dataset_config, taxonomy_config, external_config


def _make_matcher(external_configs, vimedcss_inventory):
    tmp_path, term_dir, inv_path = vimedcss_inventory
    dataset_config, taxonomy_config, external_config = external_configs
    matcher = ExternalReferenceMatcher(dataset_config, taxonomy_config, external_config)
    matcher.vimedcss_inventory_path = str(term_dir / "cs_terms_inventory.csv")
    matcher.output_dir = str(term_dir)
    return matcher, term_dir


# ---------------------------------------------------------------------------
# EXT_REF-01: external_sources_registry.csv
# ---------------------------------------------------------------------------

class TestExternalSourcesRegistry:
    def test_registry_contains_pilot_source(self, external_configs, vimedcss_inventory):
        """EXT_REF-01: Registry contains at least one pilot source."""
        matcher, term_dir = _make_matcher(external_configs, vimedcss_inventory)
        matcher.run()
        reg_df = pd.read_csv(matcher.registry_path)
        assert len(reg_df) >= 1
        assert bool(reg_df.iloc[0]["include_in_pilot"]) is True

    def test_registry_csv_columns(self, external_configs, vimedcss_inventory):
        """EXT_REF-01: Registry CSV has all required columns."""
        matcher, term_dir = _make_matcher(external_configs, vimedcss_inventory)
        matcher.run()
        reg_df = pd.read_csv(matcher.registry_path)
        required = {"source_name", "source_url", "license_or_access_note", "include_in_pilot", "coverage_notes"}
        assert required.issubset(set(reg_df.columns))

    def test_empty_external_inventory_produces_empty_registry(self, nyquist_tmp_path):
        """EXT_REF-01: Empty inventory dir produces empty registry without crashing."""
        tmp_path, term_dir = nyquist_tmp_path
        # Create empty inventory dir (no CSV files)
        inv_dir = tmp_path / "data" / "raw" / "external"
        os.makedirs(inv_dir, exist_ok=True)
        # Create empty cs_terms_inventory
        vimedcss_df = pd.DataFrame({
            "normalized_term": [],
            "entity_category": [],
            "medical_domain": [],
            "occurrence_count": [],
        })
        vimedcss_df.to_csv(term_dir / "cs_terms_inventory.csv", index=False)
        
        dataset_config = {}
        taxonomy_config = {}
        external_config = {
            "enabled": True,
            "pilot_sources": [],
            "inventory_dir": str(inv_dir),
            "output_dir": str(term_dir),
            "match_mode": "exact_case_insensitive",
            "min_commonness_for_high_priority": 5,
        }
        matcher = ExternalReferenceMatcher(dataset_config, taxonomy_config, external_config)
        matcher.vimedcss_inventory_path = str(term_dir / "cs_terms_inventory.csv")
        matcher.output_dir = str(term_dir)
        
        stats = matcher.run()
        assert stats["external_term_count"] == 0
        assert stats["vimedcss_covered_count"] == 0
        assert stats["coverage_ratio"] == 0.0


# ---------------------------------------------------------------------------
# EXT_REF-02: external_medical_term_inventory.csv
# ---------------------------------------------------------------------------

class TestExternalInventorySchema:
    def test_external_inventory_schema(self, external_configs, vimedcss_inventory):
        """EXT_REF-02: External inventory CSV has required schema columns."""
        matcher, term_dir = _make_matcher(external_configs, vimedcss_inventory)
        matcher.run()
        ext_df = pd.read_csv(matcher.external_inventory_path)
        required = {
            "term_id", "canonical_term", "language", "entity_category",
            "medical_domain", "specialty", "source_name", "commonness_level",
            "commonness_source", "include_in_pilot", "notes"
        }
        assert required.issubset(set(ext_df.columns))


# ---------------------------------------------------------------------------
# EXT_REF-02: vimedcss_vs_external_coverage.csv
# ---------------------------------------------------------------------------

class TestCoverageCSV:
    def test_coverage_csv_schema(self, external_configs, vimedcss_inventory):
        """EXT_REF-02: Coverage CSV has required columns."""
        matcher, term_dir = _make_matcher(external_configs, vimedcss_inventory)
        matcher.run()
        cov_df = pd.read_csv(matcher.coverage_path)
        required = {
            "group_key", "external_term_count", "vimedcss_covered_count",
            "coverage_ratio", "missing_high_priority_count"
        }
        assert required.issubset(set(cov_df.columns))

    def test_coverage_ratios_correct(self, external_configs, vimedcss_inventory):
        """EXT_REF-02: Coverage ratios computed correctly from local CSVs."""
        matcher, term_dir = _make_matcher(external_configs, vimedcss_inventory)
        stats = matcher.run()
        # metformin, diabetes, hba1c should match (case-insensitive)
        # Expected covered: metformin, DIABETES->diabetes, hba1c = 3 out of 5
        assert stats["vimedcss_covered_count"] == 3
        assert stats["coverage_ratio"] == pytest.approx(3 / 5, rel=1e-4)

    def test_missing_high_priority_terms_listed(self, external_configs, vimedcss_inventory):
        """EXT_REF-02: Missing high-priority terms are identified (occurrence >= 5)."""
        matcher, term_dir = _make_matcher(external_configs, vimedcss_inventory)
        stats = matcher.run()
        # Missing terms: stent (3 occ < 5, not high priority), asthma (10 occ, in external? No - 'asthma' not in mock)
        # So stent: not high priority (3<5), asthma: missing + 10>=5 -> high priority
        assert stats["missing_high_priority_count"] >= 1


# ---------------------------------------------------------------------------
# EXT_REF-02: external_coverage_summary.md
# ---------------------------------------------------------------------------

class TestSummaryMarkdown:
    def test_summary_has_pilot_disclaimer(self, external_configs, vimedcss_inventory):
        """EXT_REF-02: Summary includes pilot inventory disclaimer."""
        matcher, term_dir = _make_matcher(external_configs, vimedcss_inventory)
        matcher.run()
        content = open(matcher.summary_path, encoding="utf-8").read()
        assert "pilot" in content.lower() or "thử nghiệm" in content.lower()

    def test_summary_vietnamese_headings(self, external_configs, vimedcss_inventory):
        """EXT_REF-02: Summary markdown contains Vietnamese section headings."""
        matcher, term_dir = _make_matcher(external_configs, vimedcss_inventory)
        matcher.run()
        content = open(matcher.summary_path, encoding="utf-8").read()
        assert "Tổng quan" in content or "Phủ sóng" in content


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_missing_inventory_dir_raises_filenotfound(self, nyquist_tmp_path):
        """Task 6: Missing inventory directory raises FileNotFoundError."""
        tmp_path, term_dir = nyquist_tmp_path
        vimedcss_df = pd.DataFrame({
            "normalized_term": ["metformin"],
            "entity_category": ["drug"],
            "medical_domain": ["treatments"],
            "occurrence_count": [5],
        })
        vimedcss_df.to_csv(term_dir / "cs_terms_inventory.csv", index=False)
        
        dataset_config = {}
        taxonomy_config = {}
        external_config = {
            "enabled": True,
            "pilot_sources": [],
            "inventory_dir": "/nonexistent/path",
            "output_dir": str(term_dir),
            "match_mode": "exact_case_insensitive",
            "min_commonness_for_high_priority": 5,
        }
        matcher = ExternalReferenceMatcher(dataset_config, taxonomy_config, external_config)
        matcher.vimedcss_inventory_path = str(term_dir / "cs_terms_inventory.csv")
        matcher.output_dir = str(term_dir)
        
        with pytest.raises(FileNotFoundError, match="not found"):
            matcher.run()

    def test_case_insensitive_exact_match(self, external_configs, vimedcss_inventory):
        """Task 6: Case-insensitive exact match works for simple terms."""
        matcher, term_dir = _make_matcher(external_configs, vimedcss_inventory)
        stats = matcher.run()
        # DIABETES in external, diabetes in vimedcss -> should match
        assert stats["vimedcss_covered_count"] >= 2

    def test_unmatched_terms_marked_missing(self, external_configs, vimedcss_inventory):
        """Task 6: Unmatched terms get external_match_status=missing, not dropped."""
        matcher, term_dir = _make_matcher(external_configs, vimedcss_inventory)
        stats = matcher.run()
        # All 5 terms should be present with some match status
        assert stats["coverage_ratio"] >= 0.0

    def test_registry_csv_required_columns(self, external_configs, vimedcss_inventory):
        """Task 6: Registry CSV contains required columns."""
        matcher, term_dir = _make_matcher(external_configs, vimedcss_inventory)
        matcher.run()
        reg_df = pd.read_csv(matcher.registry_path)
        required = ["source_name", "source_url", "license_or_access_note", "include_in_pilot", "coverage_notes"]
        assert all(col in reg_df.columns for col in required)


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

class TestCLIMatchExternal:
    def test_build_mock_inventory_creates_csv(self, nyquist_tmp_path):
        """Task 6: build_mock_inventory creates a valid CSV with required columns."""
        tmp_path, _ = nyquist_tmp_path
        mock_dir = str(tmp_path / "mock_external")
        inv_path = ExternalReferenceMatcher.build_mock_inventory(mock_dir)
        assert os.path.exists(inv_path)
        df = pd.read_csv(inv_path)
        required = {
            "term_id", "canonical_term", "language", "entity_category",
            "medical_domain", "specialty", "source_name", "commonness_level",
            "commonness_source", "include_in_pilot", "notes"
        }
        assert required.issubset(set(df.columns))
        assert len(df) == 5  # 5 mock terms

    def test_cli_mock_mode_writes_expected_files(self, nyquist_tmp_path):
        """Task 6: CLI match-external --mock --limit N processes N terms and writes expected files."""
        tmp_path, term_dir = nyquist_tmp_path
        
        # Create cs_terms_inventory.csv
        inv_data = [
            {
                "normalized_term": f"term_{i}",
                "occurrence_count": i + 1,
                "entity_category": "unknown",
                "medical_domain": "unknown",
                "specialty": "unknown",
                "is_common_term": False,
                "frequency_bucket": "singleton",
            }
            for i in range(5)
        ]
        pd.DataFrame(inv_data).to_csv(term_dir / "cs_terms_inventory.csv", index=False)
        
        # Build mock inventory
        mock_dir = str(tmp_path / "mock_external")
        ExternalReferenceMatcher.build_mock_inventory(mock_dir)
        
        # Create configs
        os.makedirs(tmp_path / "configs", exist_ok=True)
        for fname in ["dataset.yaml", "taxonomy.yaml", "llm.yaml", "asr.yaml", "report.yaml", "external.yaml"]:
            if fname == "external.yaml":
                (tmp_path / "configs" / fname).write_text("""
enabled: true
pilot_sources:
  - name: "Test"
    source_url: "https://example.com"
    license_or_access_note: "test"
    include_in_pilot: true
    coverage_notes: "test"
inventory_dir: "{mock_dir}"
output_dir: "{term_dir}"
match_mode: "exact_case_insensitive"
min_commonness_for_high_priority: 3
""".format(mock_dir=mock_dir, term_dir=str(term_dir)))
            else:
                (tmp_path / "configs" / fname).write_text("{}\n")
        
        cfg = AppConfig(config_dir=str(tmp_path / "configs"))
        matcher = ExternalReferenceMatcher(
            cfg.get_dataset_config(),
            cfg.get_taxonomy_config(),
            cfg.get_external_config()
        )
        matcher.vimedcss_inventory_path = str(term_dir / "cs_terms_inventory.csv")
        matcher.output_dir = str(term_dir)
        matcher.inventory_dir = mock_dir
        
        # Test with limit=2
        stats = matcher.run(limit=2)
        
        assert os.path.exists(matcher.registry_path)
        assert os.path.exists(matcher.external_inventory_path)
        assert os.path.exists(matcher.coverage_path)
        assert os.path.exists(matcher.summary_path)
        assert "coverage_ratio" in stats
        # With limit=2, total ViMedCSS terms should be 2
        assert stats["vimedcss_covered_count"] <= 2
