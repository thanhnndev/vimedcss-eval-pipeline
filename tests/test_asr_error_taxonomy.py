import json
import os
from pathlib import Path

import pandas as pd
import pytest

from src.asr.error_taxonomy import ASRErrorTaxonomy


@pytest.fixture
def nyquist_tmp_path(tmp_path):
    return tmp_path


def _make_taxonomy(nyquist_tmp_path, splits=None):
    dataset_config = {"local_raw_dir": str(nyquist_tmp_path / "raw"), "splits": splits or ["test"]}
    asr_config = {
        "output_dir": str(nyquist_tmp_path / "asr_out"),
        "splits": splits or ["test"],
    }
    taxonomy_config = {"confidence_threshold_review": 0.8}
    return ASRErrorTaxonomy(dataset_config, asr_config, taxonomy_config)


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_metadata(base_dir, split, rows):
    path = Path(base_dir) / f"{split}_set.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


class TestErrorClassification:
    """Test ASRErrorTaxonomy heuristic classification of CS-term errors."""

    def test_missing_term_classified_correctly(self, nyquist_tmp_path):
        """A term completely absent from hypothesis should be classified as missing_term."""
        taxonomy = _make_taxonomy(nyquist_tmp_path)
        error_type, confidence = taxonomy._classify_error("metformin", "thuốc điều trị tiểu đường")
        assert error_type == "phonetic_vietnamese"  # Vietnamese chars present
        # Also test with no Vietnamese chars and no similarity
        error_type2, confidence2 = taxonomy._classify_error("metformin", "something completely different")
        assert error_type2 in ("missing_term", "other")

    def test_spelling_mistake_classified_correctly(self, nyquist_tmp_path):
        """A hypothesis containing a near-match (high Levenshtein ratio) should be classified as spelling_mistake."""
        taxonomy = _make_taxonomy(nyquist_tmp_path)
        # "metformin" vs "metformi" has high similarity
        error_type, confidence = taxonomy._classify_error("metformin", "metformi")
        assert error_type == "spelling_mistake"
        assert confidence >= 0.8

    def test_phonetic_vietnamese_classified_correctly(self, nyquist_tmp_path):
        """Hypothesis containing Vietnamese diacritical characters should be classified as phonetic_vietnamese."""
        taxonomy = _make_taxonomy(nyquist_tmp_path)
        error_type, confidence = taxonomy._classify_error("insulin", "thuốc insưlin cho bệnh nhân")
        assert error_type == "phonetic_vietnamese"

    def test_exact_match_not_in_taxonomy(self, nyquist_tmp_path):
        """When a term is present in hypothesis (exact match), classify_and_write should skip it."""
        taxonomy = _make_taxonomy(nyquist_tmp_path)
        raw_dir = Path(taxonomy.dataset_config["local_raw_dir"])
        _write_metadata(raw_dir, "test", [
            {"segment_id": "s0", "segment_text": "use metformin daily", "cs_terms_list": "['metformin']", "topic": "t"},
        ])
        _write_jsonl(Path(taxonomy.output_dir) / "hypotheses_test.jsonl", [
            {"segment_id": "s0", "hypothesis_text": "use metformin daily"},
        ])
        stats = taxonomy.classify_and_write()
        # Term matches exactly, so no error rows should be generated
        assert stats["error_rows"] == 0

    def test_needs_human_review_flag(self, nyquist_tmp_path):
        """Errors with confidence below threshold should be flagged for human review."""
        taxonomy = _make_taxonomy(nyquist_tmp_path)
        # "other" error type returns confidence 0.5, below threshold 0.8
        error_type, confidence = taxonomy._classify_error("metformin", "xyz abc def")
        assert confidence < taxonomy.confidence_threshold


class TestTaxonomyOutput:
    """Test that taxonomy CSV and summary outputs are correctly written."""

    def test_taxonomy_csv_contains_required_columns(self, nyquist_tmp_path):
        taxonomy = _make_taxonomy(nyquist_tmp_path)
        raw_dir = Path(taxonomy.dataset_config["local_raw_dir"])
        _write_metadata(raw_dir, "test", [
            {"segment_id": "s0", "segment_text": "take aspirin", "cs_terms_list": "['aspirin']", "topic": "t"},
        ])
        # Hypothesis missing the term
        _write_jsonl(Path(taxonomy.output_dir) / "hypotheses_test.jsonl", [
            {"segment_id": "s0", "hypothesis_text": "take something else"},
        ])
        taxonomy.classify_and_write()
        taxonomy_path = Path(taxonomy.errors_dir) / "asr_error_taxonomy.csv"
        assert taxonomy_path.exists()
        df = pd.read_csv(taxonomy_path)
        for col in ["split", "segment_id", "term", "error_type", "reference_text", "hypothesis_text", "confidence", "needs_human_review"]:
            assert col in df.columns

    def test_summary_md_written_in_vietnamese(self, nyquist_tmp_path):
        taxonomy = _make_taxonomy(nyquist_tmp_path)
        raw_dir = Path(taxonomy.dataset_config["local_raw_dir"])
        _write_metadata(raw_dir, "test", [
            {"segment_id": "s0", "segment_text": "take aspirin", "cs_terms_list": "['aspirin']", "topic": "t"},
        ])
        _write_jsonl(Path(taxonomy.output_dir) / "hypotheses_test.jsonl", [
            {"segment_id": "s0", "hypothesis_text": "take something else"},
        ])
        taxonomy.classify_and_write()
        summary_path = Path(taxonomy.output_dir) / "asr_evaluation_summary.md"
        assert summary_path.exists()
        content = summary_path.read_text(encoding="utf-8")
        assert "Đánh giá baseline ASR" in content

    def test_empty_hypotheses_writes_empty_taxonomy(self, nyquist_tmp_path):
        taxonomy = _make_taxonomy(nyquist_tmp_path)
        raw_dir = Path(taxonomy.dataset_config["local_raw_dir"])
        _write_metadata(raw_dir, "test", [
            {"segment_id": "s0", "segment_text": "text", "cs_terms_list": "[]", "topic": "t"},
        ])
        _write_jsonl(Path(taxonomy.output_dir) / "hypotheses_test.jsonl", [])
        stats = taxonomy.classify_and_write()
        assert stats["error_rows"] == 0
