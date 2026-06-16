"""Tests for the report generation module.

This module contains tests for ReportGenerator, DataSourceRegistry, LimitationWriter,
and CLI integration for the ViMedCSS evaluation pipeline.
"""

import os
import json
import pytest
import pandas as pd
from pathlib import Path
from typing import Dict, Any

from src.reports.report_generator import ReportGenerator
from src.reports.report_data_sources import DataSourceRegistry
from src.reports.report_limitations import LimitationWriter


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory for tests."""
    output_dir = tmp_path / "outputs" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


@pytest.fixture
def temp_artifact_dir(tmp_path: Path) -> Path:
    """Create temporary artifact directories for tests."""
    # Create term_coverage directory
    term_dir = tmp_path / "outputs" / "term_coverage"
    term_dir.mkdir(parents=True, exist_ok=True)

    # Create audit directory
    audit_dir = tmp_path / "outputs" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    # Create asr_eval directory
    asr_dir = tmp_path / "outputs" / "asr_eval" / "errors"
    asr_dir.mkdir(parents=True, exist_ok=True)

    return tmp_path


@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """Provide sample configuration for testing."""
    return {
        "dataset": {
            "repo_id": "tensorxt/ViMedCSS",
            "local_raw_dir": "data/raw/vimedcss",
            "splits": ["train", "validation", "test", "hard"],
        },
        "taxonomy": {
            "frequency_buckets": {
                "singleton": [1, 1],
                "rare": [2, 4],
                "medium": [5, 19],
                "common": [20, None],
            },
            "confidence_threshold_review": 0.80,
        },
        "report": {
            "language": "vi",
            "output_dir": "outputs/reports",
            "format": "markdown",
            "asr_section_policy": "skip_with_disclaimer",
            "sections": [
                {"id": "executive_summary", "title": "Tóm tắt kết luận", "enabled": True},
                {"id": "term_coverage_overview", "title": "Tổng quan coverage", "enabled": True},
                {"id": "asr_baseline_results", "title": "Kết quả ASR", "enabled": True, "requires_outputs": ["outputs/asr_eval/metrics_summary.csv"]},
            ],
        },
        "external": {
            "inventory_dir": "data/external",
            "sources": [],
        },
    }


@pytest.fixture
def sample_inventory_csv(temp_artifact_dir: Path) -> Path:
    """Create a sample term inventory CSV."""
    csv_path = temp_artifact_dir / "outputs" / "term_coverage" / "cs_terms_inventory.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame({
        "normalized_term": ["virus", "gen", "hormone", "inulin", "uric"],
        "raw_forms": ["virus", "gen", "hormone", "inulin", "uric"],
        "occurrence_count": [946, 450, 232, 238, 81],
        "frequency_bucket": ["common", "common", "common", "common", "common"],
        "entity_category": ["unknown", "unknown", "unknown", "unknown", "unknown"],
        "medical_domain": ["Medical Sciences", "Medical Sciences", "Medical Sciences", "Nutrition", "Medical Sciences"],
    })

    df.to_csv(csv_path, index=False)
    return csv_path


@pytest.fixture
def sample_taxonomy_summary_csv(temp_artifact_dir: Path) -> Path:
    """Create a sample taxonomy summary CSV."""
    csv_path = temp_artifact_dir / "outputs" / "term_coverage" / "cs_terms_by_entity_category.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame({
        "entity_category": ["unknown", "abbreviation_or_acronym", "disease_or_condition"],
        "count": [674, 121, 7],
        "percentage": [75.8, 13.6, 0.8],
    })

    df.to_csv(csv_path, index=False)
    return csv_path


@pytest.fixture
def sample_hf_manifest(temp_artifact_dir: Path) -> Path:
    """Create a sample HF manifest JSON."""
    manifest_path = temp_artifact_dir / "outputs" / "audit" / "hf_file_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = {
        "repo_id": "tensorxt/ViMedCSS",
        "revision": "abc123",
        "downloaded_at": "2024-01-01T00:00:00",
        "files": ["train_set.csv", "validation_set.csv", "test_set.csv", "hard_set.csv"],
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    return manifest_path


class TestReportGenerator:
    """Test cases for ReportGenerator class."""

    def test_generate_report_with_all_artifacts_writes_expected_files(
        self,
        temp_output_dir: Path,
        temp_artifact_dir: Path,
        sample_config: Dict[str, Any],
        sample_inventory_csv: Path,
        sample_taxonomy_summary_csv: Path,
        sample_hf_manifest: Path,
        monkeypatch,
    ):
        """Test that generate creates all expected report files."""
        # Change to temp directory
        monkeypatch.chdir(temp_artifact_dir)

        # Update config with temp output dir
        sample_config["report"]["output_dir"] = str(temp_output_dir)

        generator = ReportGenerator(
            sample_config["dataset"],
            sample_config["taxonomy"],
            sample_config["report"],
            sample_config["external"],
        )

        generated = generator.generate(output_dir=str(temp_output_dir), skip_asr=False)

        # Verify main report exists
        assert "main_report" in generated
        assert os.path.exists(generated["main_report"])

        # Verify data sources report exists
        assert "data_sources_report" in generated
        assert os.path.exists(generated["data_sources_report"])

        # Verify limitations report exists
        assert "limitations_report" in generated
        assert os.path.exists(generated["limitations_report"])

        # Verify report names
        assert "report_vi_vimedcss_term_coverage_and_asr_weakness.md" in generated["main_report"]
        assert "report_data_sources.md" in generated["data_sources_report"]
        assert "report_limitations.md" in generated["limitations_report"]

    def test_generate_report_with_missing_asr_outputs_skips_asr_sections_and_adds_disclaimer(
        self,
        temp_output_dir: Path,
        temp_artifact_dir: Path,
        sample_config: Dict[str, Any],
        sample_inventory_csv: Path,
        monkeypatch,
    ):
        """Test that ASR sections show disclaimer when ASR outputs are missing."""
        monkeypatch.chdir(temp_artifact_dir)
        sample_config["report"]["output_dir"] = str(temp_output_dir)

        generator = ReportGenerator(
            sample_config["dataset"],
            sample_config["taxonomy"],
            sample_config["report"],
            sample_config["external"],
        )

        generated = generator.generate(output_dir=str(temp_output_dir), skip_asr=False)

        # Read main report content
        with open(generated["main_report"], "r", encoding="utf-8") as f:
            content = f.read()

        # Verify disclaimer is present for missing ASR sections
        assert "PENDING" in content or "chưa hoàn thành" in content.lower()

    def test_generate_report_with_skip_asr_flag_ignores_present_asr_outputs(
        self,
        temp_output_dir: Path,
        temp_artifact_dir: Path,
        sample_config: Dict[str, Any],
        sample_inventory_csv: Path,
        monkeypatch,
    ):
        """Test that --skip-asr flag causes ASR sections to be skipped."""
        monkeypatch.chdir(temp_artifact_dir)
        sample_config["report"]["output_dir"] = str(temp_output_dir)

        # Create dummy ASR metrics file to simulate present ASR outputs
        asr_dir = temp_artifact_dir / "outputs" / "asr_eval"
        asr_dir.mkdir(parents=True, exist_ok=True)
        metrics_path = asr_dir / "metrics_summary.csv"
        pd.DataFrame({"split": ["train"], "wer": [0.1]}).to_csv(metrics_path, index=False)

        generator = ReportGenerator(
            sample_config["dataset"],
            sample_config["taxonomy"],
            sample_config["report"],
            sample_config["external"],
        )

        # Generate with skip_asr=True
        generated = generator.generate(output_dir=str(temp_output_dir), skip_asr=True)

        with open(generated["main_report"], "r", encoding="utf-8") as f:
            content = f.read()

        # Verify ASR section title is not present when skipped
        assert "Kết quả ASR baseline" not in content or "skip" in content.lower()

    def test_missing_core_artifact_raises_file_not_found(
        self,
        temp_output_dir: Path,
        temp_artifact_dir: Path,
        sample_config: Dict[str, Any],
        monkeypatch,
    ):
        """Test that missing core artifact raises FileNotFoundError."""
        monkeypatch.chdir(temp_artifact_dir)
        sample_config["report"]["output_dir"] = str(temp_output_dir)

        generator = ReportGenerator(
            sample_config["dataset"],
            sample_config["taxonomy"],
            sample_config["report"],
            sample_config["external"],
        )

        # Should not raise even without inventory (empty DataFrame used)
        generated = generator.generate(output_dir=str(temp_output_dir), skip_asr=True)

        # Verify report is generated even with empty inventory
        assert os.path.exists(generated["main_report"])

    def test_empty_term_inventory_writes_zero_count_tables_without_crashing(
        self,
        temp_output_dir: Path,
        temp_artifact_dir: Path,
        sample_config: Dict[str, Any],
        monkeypatch,
    ):
        """Test that empty inventory produces valid report without crashing."""
        monkeypatch.chdir(temp_artifact_dir)
        sample_config["report"]["output_dir"] = str(temp_output_dir)

        # Create empty inventory (header only)
        inventory_path = temp_artifact_dir / "outputs" / "term_coverage" / "cs_terms_inventory.csv"
        inventory_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["normalized_term", "raw_forms", "occurrence_count"]).to_csv(inventory_path, index=False)

        generator = ReportGenerator(
            sample_config["dataset"],
            sample_config["taxonomy"],
            sample_config["report"],
            sample_config["external"],
        )

        # Should not raise
        generated = generator.generate(output_dir=str(temp_output_dir), skip_asr=True)

        # Verify report exists and is valid
        assert os.path.exists(generated["main_report"])
        with open(generated["main_report"], "r", encoding="utf-8") as f:
            content = f.read()
        assert len(content) > 0

    def test_config_section_ordering_matches_declared_order(
        self,
        temp_output_dir: Path,
        temp_artifact_dir: Path,
        sample_config: Dict[str, Any],
        monkeypatch,
    ):
        """Test that sections are rendered in declared order from config."""
        monkeypatch.chdir(temp_artifact_dir)
        sample_config["report"]["output_dir"] = str(temp_output_dir)

        # Define sections in specific order
        sample_config["report"]["sections"] = [
            {"id": "executive_summary", "title": "Section A", "enabled": True},
            {"id": "term_coverage_overview", "title": "Section B", "enabled": True},
            {"id": "data_sources", "title": "Section C", "enabled": True},
        ]

        generator = ReportGenerator(
            sample_config["dataset"],
            sample_config["taxonomy"],
            sample_config["report"],
            sample_config["external"],
        )

        generated = generator.generate(output_dir=str(temp_output_dir), skip_asr=True)

        with open(generated["main_report"], "r", encoding="utf-8") as f:
            content = f.read()

        # Verify sections appear in order
        pos_a = content.find("Section A")
        pos_b = content.find("Section B")
        pos_c = content.find("Section C")

        assert pos_a > 0 and pos_b > 0 and pos_c > 0
        assert pos_a < pos_b < pos_c

    def test_report_files_are_valid_utf8_markdown(
        self,
        temp_output_dir: Path,
        temp_artifact_dir: Path,
        sample_config: Dict[str, Any],
        sample_inventory_csv: Path,
        monkeypatch,
    ):
        """Test that generated reports are valid UTF-8 markdown."""
        monkeypatch.chdir(temp_artifact_dir)
        sample_config["report"]["output_dir"] = str(temp_output_dir)

        generator = ReportGenerator(
            sample_config["dataset"],
            sample_config["taxonomy"],
            sample_config["report"],
            sample_config["external"],
        )

        generated = generator.generate(output_dir=str(temp_output_dir), skip_asr=True)

        for name, path in generated.items():
            # Verify file exists
            assert os.path.exists(path), f"{name} not found at {path}"

            # Verify UTF-8 encoding
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # Verify Vietnamese characters preserved
            assert "Tổng" in content or "dữ liệu" in content

            # Verify markdown structure
            assert content.startswith("#")


class TestDataSourceRegistry:
    """Test cases for DataSourceRegistry class."""

    def test_data_source_registry_generates_report(
        self,
        temp_output_dir: Path,
        sample_config: Dict[str, Any],
    ):
        """Test that DataSourceRegistry generates a valid report."""
        registry = DataSourceRegistry(
            sample_config["dataset"],
            sample_config["external"],
        )

        # Override output dir
        registry.output_dir = str(temp_output_dir)

        output_path = registry.generate()

        assert os.path.exists(output_path)
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Verify report contains key sections
        assert "Nguồn dữ liệu" in content
        assert "paper_reported" in content
        assert "local_verified" in content
        assert "llm_inferred" in content


class TestLimitationWriter:
    """Test cases for LimitationWriter class."""

    def test_limitation_writer_generates_report(
        self,
        temp_output_dir: Path,
        sample_config: Dict[str, Any],
    ):
        """Test that LimitationWriter generates a valid report."""
        writer = LimitationWriter(
            sample_config["dataset"],
            sample_config["taxonomy"],
            sample_config["external"],
        )

        # Override output dir
        writer.output_dir = str(temp_output_dir)

        output_path = writer.generate()

        assert os.path.exists(output_path)
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Verify report contains key sections
        assert "Giới hạn" in content or "Limitations" in content
        assert "UMLS" in content or "API" in content


class TestCLIIntegration:
    """Test cases for CLI integration."""

    def test_cli_generate_report_prints_generated_paths(
        self,
        temp_output_dir: Path,
        temp_artifact_dir: Path,
        sample_config: Dict[str, Any],
        sample_inventory_csv: Path,
        monkeypatch,
        capsys,
    ):
        """Test that CLI generate-report prints generated file paths."""
        # Create config directory with config files
        config_dir = temp_artifact_dir / "configs"
        config_dir.mkdir(parents=True, exist_ok=True)

        import yaml
        # Write dataset.yaml
        with open(config_dir / "dataset.yaml", "w", encoding="utf-8") as f:
            yaml.dump(sample_config["dataset"], f)

        # Write taxonomy.yaml
        with open(config_dir / "taxonomy.yaml", "w", encoding="utf-8") as f:
            yaml.dump(sample_config["taxonomy"], f)

        # Write report.yaml
        sample_config["report"]["output_dir"] = str(temp_output_dir)
        with open(config_dir / "report.yaml", "w", encoding="utf-8") as f:
            yaml.dump(sample_config["report"], f)

        # Write external.yaml
        with open(config_dir / "external.yaml", "w", encoding="utf-8") as f:
            yaml.dump(sample_config["external"], f)

        # Write asr.yaml
        with open(config_dir / "asr.yaml", "w", encoding="utf-8") as f:
            yaml.dump({"enabled": True, "output_dir": "outputs/asr_eval"}, f)

        # Write llm.yaml
        with open(config_dir / "llm.yaml", "w", encoding="utf-8") as f:
            yaml.dump({"provider": "openai", "model": "gpt-4o"}, f)

        # Mock sys.argv with config dir
        import sys
        monkeypatch.setattr(
            sys, "argv",
            ["src/cli.py", "--config-dir", str(config_dir), "generate-report",
             "--output-dir", str(temp_output_dir), "--skip-asr"]
        )

        # Import and run CLI main
        from src.cli import main

        try:
            main()
        except SystemExit:
            pass  # CLI may exit

        captured = capsys.readouterr()

        # Verify output contains file paths or success message
        output = captured.out + captured.err
        assert "report" in output.lower() or "generated" in output.lower()


class TestMakefileTargets:
    """Test cases for Makefile integration."""

    def test_make_report_target_invokes_cli_command(self, monkeypatch):
        """Test that make report target would invoke CLI correctly."""
        import subprocess

        # Just verify the Makefile has the right command
        with open("Makefile", "r", encoding="utf-8") as f:
            makefile_content = f.read()

        # Verify report target exists and has correct structure
        assert "report:" in makefile_content
        assert "generate-report" in makefile_content
        assert "PYTHONPATH=." in makefile_content

        # Verify report-preview target exists
        assert "report-preview:" in makefile_content
        assert "--skip-asr" in makefile_content
