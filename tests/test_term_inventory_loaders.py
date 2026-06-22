"""Tests for src.term_inventory.loaders module.

Tests the BaseLoader abstract class and concrete loader implementations.
Each loader produces a DataFrame conforming to the MedicalTermRecord schema.
"""
import pandas as pd
import pytest
from src.term_inventory.loaders import (
    AbbreviationLoader,
    Icd10BackboneLoader,
    OpenFdaDeviceLoader,
    RxNormLoader,
    VimedcssSeedLoader,
)
from src.term_inventory.loaders.icd10_backbone import BaseLoader as ICD10BaseLoader
from src.term_inventory.schemas import InventoryConfig


# -------------------------------------------------------------------------- #
# Fixtures
# -------------------------------------------------------------------------- #

@pytest.fixture
def icd10_csv(tmp_path):
    """Minimal ICD-10 backbone CSV with two disease rows at level='type'."""
    content = (
        "code,level,label_en,label_vi,chapter_code,chapter_label_en,"
        "chapter_label_vi,parent_code,source,source_url,fetched_at\n"
        "E11.9,type,type 2 diabetes mellitus,đái tháo đường typ 2,"
        "E11,E11,,E10,NLM,https://example.com,2026-01-01T00:00:00Z\n"
        "I10,type,essential hypertension,tăng huyết áp nguyên phát,"
        "I10,I10,,I00,NLM,https://example.com,2026-01-01T00:00:00Z\n"
    )
    f = tmp_path / "icd10_dual_language.csv"
    f.write_text(content)
    return str(f)


@pytest.fixture
def mock_config(icd10_csv, tmp_path):
    """InventoryConfig pointing to the fixture ICD-10 file and tmp output/log dirs."""
    return InventoryConfig(
        icd10_backbone_path=icd10_csv,
        output_dir=str(tmp_path / "out"),
        log_dir=str(tmp_path / "logs"),
    )


# -------------------------------------------------------------------------- #
# BaseLoader interface tests
# -------------------------------------------------------------------------- #

class TestBaseLoaderInterface:
    def test_all_loaders_inherit_from_base_loader(self):
        assert issubclass(Icd10BackboneLoader, ICD10BaseLoader)
        assert issubclass(RxNormLoader, ICD10BaseLoader)
        assert issubclass(AbbreviationLoader, ICD10BaseLoader)
        assert issubclass(VimedcssSeedLoader, ICD10BaseLoader)
        assert issubclass(OpenFdaDeviceLoader, ICD10BaseLoader)

    def test_all_loaders_have_load_method(self, mock_config):
        for loader_class in [
            Icd10BackboneLoader,
            RxNormLoader,
            AbbreviationLoader,
            OpenFdaDeviceLoader,
        ]:
            loader = loader_class(mock_config)
            assert hasattr(loader, "load")
            assert callable(loader.load)


# -------------------------------------------------------------------------- #
# Icd10BackboneLoader tests
# -------------------------------------------------------------------------- #

class TestIcd10BackboneLoaderColumns:
    def test_icd10_loader_produces_required_columns(self, mock_config):
        loader = Icd10BackboneLoader(mock_config)
        df = loader.load()

        assert "term_original" in df.columns
        assert "entity_type" in df.columns
        assert "source_name" in df.columns
        assert "review_status" in df.columns
        assert len(df) == 2

    def test_icd10_loader_missing_file_raises(self, tmp_path):
        bad_config = InventoryConfig(
            icd10_backbone_path=str(tmp_path / "nonexistent.csv"),
            output_dir=str(tmp_path / "out"),
            log_dir=str(tmp_path / "logs"),
        )
        loader = Icd10BackboneLoader(bad_config)
        with pytest.raises(FileNotFoundError):
            loader.load()


# -------------------------------------------------------------------------- #
# AbbreviationLoader tests
# -------------------------------------------------------------------------- #

class TestAbbreviationLoaderProducesExpansions:
    def test_abbreviation_loader_produces_rows_for_each_abbreviation(self, mock_config):
        # ECG + ECG expansion + MRI + MRI expansion + CT + CT expansion = 6 rows
        mock_config.abbreviation_list = ["ECG", "MRI", "CT"]
        loader = AbbreviationLoader(mock_config)
        df = loader.load()
        assert len(df) >= 6

    def test_abbreviation_loader_contains_expansions(self, mock_config):
        mock_config.abbreviation_list = ["ECG", "MRI", "CT"]
        loader = AbbreviationLoader(mock_config)
        df = loader.load()
        originals = df["term_original"].str.lower().tolist()
        # ECG expansion → "electrocardiogram"
        assert any("electrocardiogram" in t for t in originals)
        # MRI expansion → "magnetic resonance imaging"
        assert any("magnetic resonance imaging" in t for t in originals)


# -------------------------------------------------------------------------- #
# VimedcssSeedLoader tests
# -------------------------------------------------------------------------- #

class TestVimedcssSeedLoaderMissingFile:
    def test_vimedcss_seed_loader_raises_on_missing_file(self, mock_config, monkeypatch):
        # Point to a non-existent path via env var
        monkeypatch.setenv("VIMEDCSS_SEED_PATH", "/nonexistent/path.csv")
        loader = VimedcssSeedLoader(mock_config)
        with pytest.raises(FileNotFoundError):
            loader.load()


# -------------------------------------------------------------------------- #
# Required columns tests
# -------------------------------------------------------------------------- #

class TestAllLoadersRequiredCols:
    def test_icd10_required_columns(self, mock_config):
        loader = Icd10BackboneLoader(mock_config)
        df = loader.load()
        assert len(df) == 2
        for col in ICD10BaseLoader.REQUIRED_COLS:
            assert col in df.columns

    def test_rxnorm_required_columns(self, mock_config):
        loader = RxNormLoader(mock_config)
        df = loader.load()
        # Returns empty if network unavailable; column check only if rows exist
        for col in ICD10BaseLoader.REQUIRED_COLS:
            assert col in df.columns

    def test_nlm_lab_required_columns(self, mock_config):
        loader = OpenFdaDeviceLoader(mock_config)
        df = loader.load()
        for col in ICD10BaseLoader.REQUIRED_COLS:
            assert col in df.columns

    def test_abbreviation_required_columns(self, mock_config):
        mock_config.abbreviation_list = ["ECG"]
        loader = AbbreviationLoader(mock_config)
        df = loader.load()
        assert len(df) >= 1
        for col in ICD10BaseLoader.REQUIRED_COLS:
            assert col in df.columns


# -------------------------------------------------------------------------- #
# Source name tests
# -------------------------------------------------------------------------- #

class TestAbbreviationSourceName:
    def test_all_abbreviation_rows_have_abbreviation_list_source(self, mock_config):
        mock_config.abbreviation_list = ["ECG", "MRI", "CT"]
        loader = AbbreviationLoader(mock_config)
        df = loader.load()
        assert (df["source_name"] == "abbreviation_list").all()
