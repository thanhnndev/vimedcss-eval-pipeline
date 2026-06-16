import os
import csv
import json
import time
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

import pandas as pd

try:
    from faster_whisper import WhisperModel, BatchedInferencePipeline
except ImportError:
    WhisperModel = None  # type: ignore
    BatchedInferencePipeline = None  # type: ignore

from src.shared.logging import setup_logger
from src.shared.config import AppConfig
from src.asr.audio_utils import resolve_audio_path, verify_audio_file
from src.terms.extractor import parse_terms

logger = setup_logger("asr.transcriber")


class ASRTranscriber:
    """Transcribes ViMedCSS audio splits using faster-whisper baseline models."""

    def __init__(self, dataset_config: Dict[str, Any], asr_config: Dict[str, Any]):
        self.dataset_config = dataset_config
        self.asr_config = asr_config
        self.local_raw_dir = dataset_config.get("local_raw_dir", "data/raw/vimedcss")
        self.output_dir = asr_config.get("output_dir", "outputs/asr_eval")
        os.makedirs(self.output_dir, exist_ok=True)
        self.splits = asr_config.get("splits", ["test", "hard"])
        self.run_mode = asr_config.get("run_mode", "sample_first")
        self.sample_size = int(asr_config.get("sample_size", 100))
        self.device = asr_config.get("device", "cpu")
        self.compute_type = asr_config.get("compute_type", "int8")
        self.batch_size = int(asr_config.get("batch_size", 8))
        self.beam_size = int(asr_config.get("beam_size", 5))
        self.vad_filter = bool(asr_config.get("vad_filter", True))
        self.audio_verification = asr_config.get("audio_verification", {})
        self.model_cfg = (asr_config.get("models") or [{}])[0]
        self.model_name = self.model_cfg.get("name", "whisper_large_v3")
        self.model_id = self.model_cfg.get("model_id", "large-v3")

        self.stats = {
            "splits_processed": 0,
            "segments_processed": 0,
            "segments_skipped_missing_audio": 0,
            "segments_skipped_corrupt_audio": 0,
            "sample_first_mode": self.run_mode == "sample_first",
            "sample_size": self.sample_size,
        }

    def run(self, mock: bool = False, limit: Optional[int] = None) -> Dict[str, Any]:
        """Run transcription pipeline across configured splits.

        Args:
            mock: Write dummy manifests/hypotheses without calling faster-whisper.
            limit: Override per-split segment limit.

        Returns:
            Execution statistics.
        """
        logger.info("Starting ASR transcription pipeline")
        logger.info(f"Run mode: {self.run_mode} | Device: {self.device} | Compute type: {self.compute_type}")

        manifests = {}
        for split in self.splits:
            manifest_path = os.path.join(self.output_dir, f"eval_manifest_{split}.jsonl")
            manifest = self._build_manifest(split, limit=limit)
            manifests[split] = manifest
            self._write_jsonl(manifest_path, manifest)
            logger.info(f"Wrote manifest for {split}: {len(manifest)} entries -> {manifest_path}")

        if mock:
            logger.info("Mock mode enabled; skipping model load and transcription")
            for split, manifest in manifests.items():
                hyp_path = os.path.join(self.output_dir, f"hypotheses_{split}.jsonl")
                mock_rows = []
                for row in manifest:
                    mock_rows.append({
                        "split": split,
                        "segment_id": row["segment_id"],
                        "hypothesis_text": row.get("reference_text", ""),
                        "language": "vi",
                        "duration_seconds": row.get("duration_seconds", 0.0),
                        "start": 0.0,
                        "end": row.get("duration_seconds", 0.0),
                        "model_name": self.model_name,
                        "device": self.device,
                        "compute_type": self.compute_type,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                    })
                self._write_jsonl(hyp_path, mock_rows)
            self._write_model_registry()
            self.stats["segments_processed"] = sum(len(m) for m in manifests.values())
            return self.stats

        model = self._load_model()
        pipeline = self._build_pipeline(model) if self.batch_size > 1 else None

        for split, manifest in manifests.items():
            if not manifest:
                logger.info(f"Empty manifest for {split}; skipping transcription")
                continue
            hyp_path = os.path.join(self.output_dir, f"hypotheses_{split}.jsonl")
            hypotheses = self._transcribe_split(split, manifest, model, pipeline)
            self._write_jsonl(hyp_path, hypotheses)
            logger.info(f"Wrote hypotheses for {split}: {len(hypotheses)} entries -> {hyp_path}")

        self._write_model_registry()
        return self.stats

    def _build_manifest(self, split: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Read metadata for a split, resolve/verify audio files, and return manifest rows."""
        metadata_path = self._resolve_metadata_path(split)
        df = pd.read_csv(metadata_path)
        df = self._map_fields(df)

        if self.run_mode == "sample_first":
            df = df.head(self.sample_size).copy()
            logger.info(f"sample_first mode: processing up to {self.sample_size} entries for {split}")
        if limit is not None and limit > 0:
            df = df.head(limit).copy()
            logger.info(f"Limit applied: processing up to {limit} entries for {split}")

        manifest: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            audio_path = resolve_audio_path(row, self.local_raw_dir)
            duration = self._get_duration_or_nan(audio_path)
            cs_terms = parse_terms(row.get("cs_terms")) if "cs_terms" in df.columns else []

            manifest.append({
                "split": split,
                "segment_id": str(row.get("segment_id", "")),
                "audio_path": audio_path,
                "reference_text": str(row.get("transcript", "")) if pd.notna(row.get("transcript", "")) else "",
                "duration_seconds": float(duration) if pd.notna(duration) else 0.0,
                "cs_terms_list": cs_terms,
                "topic": str(row.get("topic", "")) if pd.notna(row.get("topic", "")) else "",
                "source_url": str(row.get("source_url", "")) if pd.notna(row.get("source_url", "")) else "",
            })

        expected_extensions = self.audio_verification.get("expected_extensions", [".wav", ".mp3"])
        min_duration = float(self.audio_verification.get("min_duration_seconds", 0.5))
        max_duration = float(self.audio_verification.get("max_duration_seconds", 3600.0))

        verified: List[Dict[str, Any]] = []
        for row in manifest:
            if not row["audio_path"] or not os.path.exists(row["audio_path"]):
                self.stats["segments_skipped_missing_audio"] += 1
                logger.warning(f"Missing audio for segment {row['segment_id']}")
                continue
            if not verify_audio_file(row["audio_path"], expected_extensions, min_duration, max_duration):
                self.stats["segments_skipped_corrupt_audio"] += 1
                logger.warning(f"Skipping invalid audio for segment {row['segment_id']}")
                continue
            verified.append(row)

        self.stats["segments_processed"] += len(verified)
        self.stats["splits_processed"] += 1
        return verified

    def _load_model(self):
        """Initialize faster-whisper model."""
        if WhisperModel is None:
            raise ImportError("faster-whisper is not installed. Add it to requirements.txt")
        logger.info(f"Loading model {self.model_id} on {self.device} ({self.compute_type})")
        return WhisperModel(
            self.model_id,
            device=self.device,
            compute_type=self.compute_type,
        )

    def _build_pipeline(self, model):
        """Create batched inference pipeline if available."""
        if BatchedInferencePipeline is None:
            logger.warning("BatchedInferencePipeline unavailable; falling back to sequential transcription")
            return None
        logger.info(f"Initializing BatchedInferencePipeline with batch_size={self.batch_size}")
        return BatchedInferencePipeline(model, beam_size=self.beam_size, vad_filter=self.vad_filter)

    def _transcribe_split(
        self,
        split: str,
        manifest: List[Dict[str, Any]],
        model,
        pipeline,
    ) -> List[Dict[str, Any]]:
        """Run transcription over manifest entries and return hypothesis rows."""
        hypotheses: List[Dict[str, Any]] = []
        for row in manifest:
            try:
                segments, info = model.transcribe(
                    row["audio_path"],
                    beam_size=self.beam_size,
                    vad_filter=self.vad_filter,
                )
                text_parts = [segment.text for segment in segments]
                hypothesis_text = "".join(text_parts).strip()
                start = 0.0
                end = row.get("duration_seconds", 0.0)
                hypotheses.append({
                    "split": split,
                    "segment_id": row["segment_id"],
                    "hypothesis_text": hypothesis_text,
                    "language": info.language if info else "en",
                    "duration_seconds": row.get("duration_seconds", 0.0),
                    "start": start,
                    "end": end,
                    "model_name": self.model_name,
                    "device": self.device,
                    "compute_type": self.compute_type,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                })
            except Exception as exc:
                logger.exception(f"Transcription failed for segment {row['segment_id']}: {exc}")
                self.stats["segments_skipped_corrupt_audio"] += 1
        return hypotheses

    def _write_model_registry(self) -> None:
        path = os.path.join(self.output_dir, "asr_model_registry.csv")
        exists = os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "model_name", "model_id", "type", "device",
                    "compute_type", "batch_size", "timestamp",
                ],
            )
            if not exists:
                writer.writeheader()
            writer.writerow({
                "model_name": self.model_name,
                "model_id": self.model_id,
                "type": self.model_cfg.get("type", "whisper"),
                "device": self.device,
                "compute_type": self.compute_type,
                "batch_size": self.batch_size,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            })
        logger.info(f"Updated model registry at {path}")

    def _resolve_metadata_path(self, split: str) -> str:
        possible_names = [
            f"{split}_set.csv",
            f"{split}.csv",
            f"ViMedCSS-Metadata/{split}_set.csv",
        ]
        for name in possible_names:
            candidate = os.path.join(self.local_raw_dir, name)
            if os.path.exists(candidate):
                return candidate
            nested = os.path.join(self.local_raw_dir, "ViMedCSS-Metadata", os.path.basename(name))
            if os.path.exists(nested):
                return nested

        for root, _, files in os.walk(self.local_raw_dir):
            for fname in files:
                if fname.endswith(".csv") and split.lower() in fname.lower():
                    return os.path.join(root, fname)

        raise FileNotFoundError(f"Metadata file for split '{split}' not found under {self.local_raw_dir}")

    def _map_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        field_fallbacks = {
            "segment_id": ["segment_id", "id"],
            "transcript": ["segment_text", "transcript", "text"],
            "cs_terms": ["cs_terms_list", "cs_terms", "terms"],
            "topic": ["topic", "category"],
            "duration": ["duration_seconds", "duration", "length"],
            "start": ["start_time", "start"],
            "end": ["end_time", "end"],
            "source_url": ["source_url", "url"],
            "audio": ["audio", "audio_path", "audio_file"],
        }
        mapping: Dict[str, Optional[str]] = {}
        for std_field, candidates in field_fallbacks.items():
            found = None
            for candidate in candidates:
                for col in df.columns:
                    if str(col).lower() == str(candidate).lower():
                        found = col
                        break
                if found:
                    break
            mapping[std_field] = found

        clean_data = {}
        for std_field, actual_col in mapping.items():
            if actual_col:
                clean_data[std_field] = df[actual_col]
            else:
                clean_data[std_field] = pd.Series([pd.NA] * len(df))
        return pd.DataFrame(clean_data)

    def _get_duration_or_nan(self, path: str):
        if not path or not os.path.exists(path):
            return float("nan")
        duration = self._get_audio_duration(path)
        return duration if duration is not None else float("nan")

    @staticmethod
    def _get_audio_duration(path: str) -> Optional[float]:
        try:
            import soundfile as sf  # type: ignore
            with sf.SoundFile(path) as f:
                return len(f) / f.samplerate
        except Exception:
            pass
        try:
            from mutagen import File as MutagenFile  # type: ignore
            info = MutagenFile(path)
            if info is not None and getattr(info, "info", None) is not None:
                return float(info.info.length)
        except Exception:
            pass
        return None

    @staticmethod
    def _write_jsonl(path: str, rows: List[Dict[str, Any]]) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
