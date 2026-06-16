import json
import os
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from src.asr.metrics import ASRMetrics


@pytest.fixture
def nyquist_tmp_path(tmp_path):
    return tmp_path


def _make_metrics(nyquist_tmp_path, splits=None):
    dataset_config = {"local_raw_dir": str(nyquist_tmp_path / "raw"), "splits": splits or ["test"]}
    asr_config = {
        "output_dir": str(nyquist_tmp_path / "asr_out"),
        "splits": splits or ["test"],
    }
    taxonomy_config = {}
    return ASRMetrics(dataset_config, asr_config, taxonomy_config)


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_metadata(base_dir, split, rows):
    path = Path(base_dir) / f"{split}_set.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_inventory(path: Path):
    """Write a minimal CS terms inventory CSV to the given path (inside tmp_path, never production)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "normalized_term": "metformin",
            "occurrence_count": 1,
            "entity_category": "drug",
            "medical_domain": "endocrine",
        }
    ]
    pd.DataFrame(rows).to_csv(path, index=False)


def _inventory_path_in_tmp(nyquist_tmp_path: Path) -> Path:
    """Return inventory path inside tmp_path so tests never overwrite production files."""
    return nyquist_tmp_path / "term_coverage" / "cs_terms_inventory.csv"


class TestMetricComputation:
    def test_metrics_summary_contains_required_columns(self, nyquist_tmp_path):
        metrics = _make_metrics(nyquist_tmp_path)
        raw_dir = Path(metrics.dataset_config["local_raw_dir"])
        inv_path = _inventory_path_in_tmp(nyquist_tmp_path)
        _write_inventory(inv_path)
        _write_metadata(raw_dir, "test", [
            {"segment_id": "s0", "segment_text": "hello world", "cs_terms_list": "[]", "topic": "t"},
        ])
        _write_jsonl(Path(metrics.output_dir) / "hypotheses_test.jsonl", [
            {"segment_id": "s0", "hypothesis_text": "hello world"},
        ])
        with patch.object(metrics, "_load_inventory", return_value=pd.read_csv(inv_path)):
            stats = metrics.compute_and_write()
        assert stats["splits"] == 1
        df = pd.read_csv(Path(metrics.output_dir) / "metrics_summary.csv")
        for col in ["split", "segment_count", "wer", "cer", "cs_term_recall", "cs_term_missing_rate", "cs_term_substitution_rate"]:
            assert col in df.columns

    def test_known_reference_and_hypothesis_produce_expected_rates(self, nyquist_tmp_path):
        metrics = _make_metrics(nyquist_tmp_path)
        raw_dir = Path(metrics.dataset_config["local_raw_dir"])
        inv_path = _inventory_path_in_tmp(nyquist_tmp_path)
        _write_inventory(inv_path)
        _write_metadata(raw_dir, "test", [
            {"segment_id": "s0", "segment_text": "use metformin", "cs_terms_list": "['metformin']", "topic": "t"},
        ])
        _write_jsonl(Path(metrics.output_dir) / "hypotheses_test.jsonl", [
            {"segment_id": "s0", "hypothesis_text": "use metformin"},
        ])
        with patch.object(metrics, "_load_inventory", return_value=pd.read_csv(inv_path)):
            metrics.compute_and_write()
        df = pd.read_csv(Path(metrics.output_dir) / "metrics_summary.csv")
        row = df.iloc[0]
        assert row["wer"] == 0.0
        assert row["cer"] == 0.0
        assert row["cs_term_recall"] == 1.0

    def test_empty_hypotheses_writes_header_only(self, nyquist_tmp_path):
        metrics = _make_metrics(nyquist_tmp_path)
        raw_dir = Path(metrics.dataset_config["local_raw_dir"])
        inv_path = _inventory_path_in_tmp(nyquist_tmp_path)
        _write_inventory(inv_path)
        _write_metadata(raw_dir, "test", [
            {"segment_id": "s0", "segment_text": "text", "cs_terms_list": "[]", "topic": "t"},
        ])
        _write_jsonl(Path(metrics.output_dir) / "hypotheses_test.jsonl", [])
        with patch.object(metrics, "_load_inventory", return_value=pd.read_csv(inv_path)):
            metrics.compute_and_write()
        df = pd.read_csv(Path(metrics.output_dir) / "metrics_summary.csv")
        assert len(df) == 1
        assert df.iloc[0]["segment_count"] == 0
