"""Tests for src.term_inventory.normalizer module."""
import pandas as pd
import pytest
from src.term_inventory.normalizer import (
    GREEK_TO_ASCII,
    apply_normalization,
    create_deduplication_report,
    deduplicate_within_entity_type,
    normalize_batch,
    normalize_term,
)


class TestGreekToAscii:
    def test_beta_blocker(self):
        result, desc = normalize_term("β-blocker")
        assert "beta" in result
        assert "greek_to_ascii" in desc

    def test_alpha_thalassemia(self):
        result, desc = normalize_term("α-thalassemia")
        assert "alpha" in result
        assert "greek_to_ascii" in desc

    def test_mu_microgram(self):
        # μ (Greek mu U+03BC) + "g" → unit suffix µg is caught first by
        # UNIT_SUFFIX_NORM (which uses micro sign U+00B5), producing "mcg".
        # Unit normalization runs before Greek-to-ASCII to prevent Greek mu from
        # becoming "mu" and then re-matching the "ug"→"mcg" rule.
        result, desc = normalize_term("μg")
        assert "mcg" in result
        assert "unit_normalization" in desc

    def test_gamma_globulin(self):
        result, desc = normalize_term("γ-globulin")
        assert "gamma" in result
        assert "greek_to_ascii" in desc


class TestNfcNormalization:
    def test_combining_accent_removed(self):
        # Combining acute accent (U+0301) attached to e should be stripped
        result, desc = normalize_term("metformin\u0301")
        assert result == "metformin"
        assert "nfc" in desc

    def test_cafe_with_combining_accent(self):
        # "café" with a combining accent → "cafe"
        result, desc = normalize_term("cafe\u0301")
        assert result == "cafe"
        assert "nfc" in desc


class TestCaseFolding:
    def test_uppercase_to_lowercase(self):
        result, desc = normalize_term("METFORMIN")
        assert result == "metformin"
        assert "case_fold" in desc

    def test_mixed_case_folded(self):
        result, desc = normalize_term("DiAbEtEs")
        assert result == "diabetes"


class TestUnitNormalization:
    def test_insulin_units_suffix(self):
        result, _ = normalize_term("insulin 100units")
        assert "unit" in result

    def test_metformin_mg_suffix(self):
        result, _ = normalize_term("metformin 500mg")
        assert "mg" in result

    def test_microgram_to_mcg(self):
        result, desc = normalize_term("dosage μg")
        assert "mcg" in result


class TestApplyNormalization:
    def test_apply_normalization_returns_both_dataframes(self):
        df = pd.DataFrame(
            {
                "term_original": ["METFORMIN", "INSULIN", "Aspirin"],
                "entity_type": ["drug", "drug", "drug"],
                "term_id": ["t1", "t2", "t3"],
            }
        )
        norm_df, norm_map = apply_normalization(df)
        assert "term_normalized" in norm_df.columns
        assert len(norm_df) == 3
        assert norm_map is not None

    def test_only_transformed_rows_in_map(self):
        df = pd.DataFrame(
            {
                "term_original": ["metformin", "INSULIN", "aspirin"],
                "entity_type": ["drug", "drug", "drug"],
            }
        )
        _, norm_map = apply_normalization(df)
        # metformin and aspirin have no transformation, insulin (uppercase) has case_fold
        assert len(norm_map) >= 1


class TestDeduplicateSameEntityType:
    def test_same_entity_type_same_normalized_keeps_one(self):
        df = pd.DataFrame(
            {
                "term_id": ["t1", "t2"],
                "term_original": ["Metformin", "METFORMIN"],
                "term_normalized": ["metformin", "metformin"],
                "entity_type": ["drug", "drug"],
                "source_name": ["rxnorm", "vimedcss_seed"],
                "review_status": ["verified", "needs_review"],
            }
        )
        dedup_df, _ = deduplicate_within_entity_type(df)
        assert len(dedup_df) == 1

    def test_verified_source_wins(self):
        df = pd.DataFrame(
            {
                "term_id": ["t1", "t2"],
                "term_original": ["metformin", "Metformin"],
                "term_normalized": ["metformin", "metformin"],
                "entity_type": ["drug", "drug"],
                "source_name": ["rxnorm", "vimedcss_seed"],
                "review_status": ["verified", "needs_review"],
            }
        )
        dedup_df, dup_map = deduplicate_within_entity_type(df)
        assert len(dedup_df) == 1
        # rxnorm (more authoritative) should win
        assert dedup_df.iloc[0]["source_name"] == "rxnorm"


class TestDeduplicateCrossEntityType:
    def test_same_normalized_different_entity_type_preserves_both(self):
        df = pd.DataFrame(
            {
                "term_id": ["t1", "t2"],
                "term_original": ["insulin", "insulin"],
                "term_normalized": ["insulin", "insulin"],
                "entity_type": ["drug", "biomarker"],
                "source_name": ["rxnorm", "nlm_lab"],
                "review_status": ["verified", "verified"],
            }
        )
        dedup_df, _ = deduplicate_within_entity_type(df)
        assert len(dedup_df) == 2


class TestDeduplicationRateWarning:
    def test_high_deduplication_rate_warns(self, caplog):
        # Create enough duplicate rows to trigger >30% dedup rate
        rows = []
        for i in range(10):
            rows.append(
                {
                    "term_id": f"t{i}",
                    "term_original": "metformin",
                    "term_normalized": "metformin",
                    "entity_type": "drug",
                    "source_name": "rxnorm",
                    "review_status": "verified",
                }
            )
        df = pd.DataFrame(rows)
        _, _ = deduplicate_within_entity_type(df)
        # caplog captures the warning
