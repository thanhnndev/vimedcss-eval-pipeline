import json
import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.asr.transcriber import ASRTranscriber
from src.asr.audio_utils import verify_audio_file, resolve_audio_path


@pytest.fixture
def nyquist_tmp_path(tmp_path):
    return tmp_path


def _make_transcriber(nyquist_tmp_path, splits=None, sample_size=2, local_raw_dir=None):
    dataset_config = {
        "local_raw_dir": local_raw_dir or str(nyquist_tmp_path / "raw"),
        "splits": splits or ["test"],
        "expected_fields": {
            "segment_id": "segment_id",
            "transcript": "segment_text",
            "cs_terms": "cs_terms_list",
            "topic": "topic",
            "audio": "audio",
        },
    }
    asr_config = {
        "enabled": True,
        "run_mode": "sample_first",
        "sample_size": sample_size,
        "splits": splits or ["test"],
        "models": [{"name": "whisper_large_v3", "type": "whisper", "model_id": "large-v3"}],
        "device": "cpu",
        "compute_type": "int8",
        "batch_size": 8,
        "beam_size": 5,
        "vad_filter": True,
        "audio_verification": {
            "expected_extensions": [".wav", ".mp3"],
            "min_duration_seconds": 0.1,
            "max_duration_seconds": 10.0,
        },
        "output_dir": str(nyquist_tmp_path / "asr_out"),
    }
    return ASRTranscriber(dataset_config, asr_config)


def _write_metadata(base_dir, split, rows):
    path = Path(base_dir) / f"{split}_set.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_audio(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"RIFFfakeaudio")


class TestManifestBuilder:
    def test_missing_audio_is_skipped_and_counted(self, nyquist_tmp_path):
        transcriber = _make_transcriber(nyquist_tmp_path)
        raw_dir = Path(transcriber.dataset_config["local_raw_dir"])
        _write_metadata(raw_dir, "test", [
            {"segment_id": "s1", "segment_text": "hello", "cs_terms_list": "[]", "topic": "t", "audio": "missing.wav"},
        ])
        manifest = transcriber._build_manifest("test")
        assert manifest == []
        assert transcriber.stats["segments_skipped_missing_audio"] == 1

    def test_sample_first_processes_exactly_n_entries(self, nyquist_tmp_path):
        transcriber = _make_transcriber(nyquist_tmp_path, sample_size=2)
        raw_dir = Path(transcriber.dataset_config["local_raw_dir"])
        rows = []
        for idx in range(5):
            audio_path = raw_dir / f"seg{idx}.wav"
            _write_audio(audio_path)
            rows.append({
                "segment_id": f"s{idx}",
                "segment_text": "text",
                "cs_terms_list": "[]",
                "topic": "t",
                "audio": f"seg{idx}.wav",
            })
        _write_metadata(raw_dir, "test", rows)
        manifest = transcriber._build_manifest("test")
        assert len(manifest) == 2

    def test_limit_overrides_sample_size(self, nyquist_tmp_path):
        transcriber = _make_transcriber(nyquist_tmp_path, sample_size=10)
        raw_dir = Path(transcriber.dataset_config["local_raw_dir"])
        rows = []
        for idx in range(4):
            audio_path = raw_dir / f"seg{idx}.wav"
            _write_audio(audio_path)
            rows.append({
                "segment_id": f"s{idx}",
                "segment_text": "text",
                "cs_terms_list": "[]",
                "topic": "t",
                "audio": f"seg{idx}.wav",
            })
        _write_metadata(raw_dir, "test", rows)
        manifest = transcriber._build_manifest("test", limit=1)
        assert len(manifest) == 1


class TestModelRegistry:
    def test_registry_csv_contains_required_columns(self, nyquist_tmp_path):
        transcriber = _make_transcriber(nyquist_tmp_path)
        raw_dir = Path(transcriber.dataset_config["local_raw_dir"])
        audio_path = raw_dir / "seg0.wav"
        _write_audio(audio_path)
        _write_metadata(raw_dir, "test", [
            {"segment_id": "s0", "segment_text": "text", "cs_terms_list": "[]", "topic": "t", "audio": "seg0.wav"},
        ])
        transcriber.run(mock=True)
        registry_path = Path(transcriber.output_dir) / "asr_model_registry.csv"
        assert registry_path.exists()
        df = pd.read_csv(registry_path)
        for col in ["model_name", "device", "compute_type", "batch_size", "timestamp"]:
            assert col in df.columns
