import os
import csv
from typing import Any, Dict, List

import pandas as pd
from difflib import SequenceMatcher

from src.shared.logging import setup_logger
from src.shared.config import AppConfig
from src.terms.extractor import clean_term

logger = setup_logger("asr.error_taxonomy")


class ASRErrorTaxonomy:
    """Classifies ASR errors for code-switching terms using conservative heuristics."""

    def __init__(self, dataset_config: Dict[str, Any], asr_config: Dict[str, Any], taxonomy_config: Dict[str, Any]):
        self.dataset_config = dataset_config
        self.asr_config = asr_config
        self.taxonomy_config = taxonomy_config
        self.output_dir = asr_config.get("output_dir", "outputs/asr_eval")
        self.errors_dir = os.path.join(self.output_dir, "errors")
        os.makedirs(self.errors_dir, exist_ok=True)
        self.confidence_threshold = float(taxonomy_config.get("confidence_threshold_review", 0.8))

    def classify_and_write(self, mock: bool = False, limit: int = None) -> Dict[str, Any]:
        """Classify errors across splits and write taxonomy CSV + Vietnamese summary."""
        splits = self.asr_config.get("splits", ["test", "hard"])
        taxonomy_rows: List[Dict[str, Any]] = []
        summary = {
            "split_records": [],
            "error_distribution": {},
            "top_failed_terms": [],
        }

        for split in splits:
            hyp_path = os.path.join(self.output_dir, f"hypotheses_{split}.jsonl")
            if not os.path.exists(hyp_path):
                continue
            ref_lookup = self._load_reference_lookup(split)
            data = self._load_jsonl(hyp_path)
            if limit is not None and limit > 0:
                data = data[:limit]

            split_rows = []
            error_counts = {"phonetic_vietnamese": 0, "spelling_mistake": 0, "missing_term": 0, "other": 0}

            for item in data:
                seg_id = item.get("segment_id", "")
                reference = ref_lookup.get(seg_id, "")
                hypothesis = item.get("hypothesis_text", "")
                terms = [clean_term(t) for t in str(reference).split(";") if str(t).strip()]
                norm_hyp = clean_term(hypothesis)

                for term in terms:
                    if term in norm_hyp:
                        continue
                    error_type, confidence = self._classify_error(term, hypothesis)
                    if confidence < self.confidence_threshold:
                        needs_review = True
                    else:
                        needs_review = False
                    split_rows.append({
                        "split": split,
                        "segment_id": seg_id,
                        "term": term,
                        "error_type": error_type,
                        "reference_text": reference,
                        "hypothesis_text": hypothesis,
                        "confidence": confidence,
                        "needs_human_review": needs_review,
                    })
                    error_counts[error_type] = error_counts.get(error_type, 0) + 1

            taxonomy_rows.extend(split_rows)
            summary["split_records"].append({
                "split": split,
                "error_count": len(split_rows),
                "error_distribution": error_counts,
            })
            for key, value in error_counts.items():
                summary["error_distribution"][key] = summary["error_distribution"].get(key, 0) + value

        taxonomy_path = os.path.join(self.errors_dir, "asr_error_taxonomy.csv")
        pd.DataFrame(taxonomy_rows).to_csv(taxonomy_path, index=False)
        logger.info(f"Wrote error taxonomy to {taxonomy_path}")

        summary_path = os.path.join(self.output_dir, "asr_evaluation_summary.md")
        self._write_summary(summary, summary_path)
        logger.info(f"Wrote ASR evaluation summary to {summary_path}")

        return {"error_rows": len(taxonomy_rows)}

    def _classify_error(self, term: str, hypothesis: str) -> tuple[str, float]:
        norm_hyp = clean_term(hypothesis)
        if not norm_hyp:
            return "missing_term", 1.0

        if term in norm_hyp:
            return "missing_term", 1.0

        ratio = SequenceMatcher(None, term, norm_hyp).ratio()
        if ratio >= 0.8:
            return "spelling_mistake", 0.9

        vietnamese_chars = set("ăâđêôơưàảãáạầẩẫấậằẳẵắặđèẻẽéẹềểễếệìỉĩíịòỏõóọồổỗốộờởỡớợùủũúụừửữứựỳỷỹýỵ")
        if any(char in vietnamese_chars for char in norm_hyp):
            return "phonetic_vietnamese", 0.75

        return "other", 0.5

    def _load_reference_lookup(self, split: str) -> Dict[str, str]:
        metadata_path = self._resolve_metadata_path(split)
        df = pd.read_csv(metadata_path)
        df = self._map_fields(df)
        lookup: Dict[str, str] = {}
        for _, row in df.iterrows():
            seg_id = str(row.get("segment_id", ""))
            transcript = row.get("transcript", "")
            lookup[seg_id] = str(transcript) if pd.notna(transcript) else ""
        return lookup

    def _resolve_metadata_path(self, split: str) -> str:
        local_raw_dir = self.dataset_config.get("local_raw_dir", "data/raw/vimedcss")
        candidates = [
            os.path.join(local_raw_dir, f"{split}_set.csv"),
            os.path.join(local_raw_dir, f"{split}.csv"),
            os.path.join(local_raw_dir, "ViMedCSS-Metadata", f"{split}_set.csv"),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
        for root, _, files in os.walk(local_raw_dir):
            for fname in files:
                if fname.endswith(".csv") and split.lower() in fname.lower():
                    return os.path.join(root, fname)
        raise FileNotFoundError(f"Metadata file for split '{split}' not found under {local_raw_dir}")

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
        }
        mapping: Dict[str, Any] = {}
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

        clean_data: Dict[str, Any] = {}
        for std_field, actual_col in mapping.items():
            if actual_col:
                clean_data[std_field] = df[actual_col]
            else:
                clean_data[std_field] = pd.Series([pd.NA] * len(df))
        return pd.DataFrame(clean_data)

    @staticmethod
    def _load_jsonl(path: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(__import__("json").loads(line))
                except Exception:
                    logger.warning(f"Skipping invalid JSONL line in {path}")
        return rows

    def _write_summary(self, summary: Dict[str, Any], path: str) -> None:
        lines = [
            "# Đánh giá baseline ASR",
            "",
            "Báo cáo này là kết quả thử nghiệm baseline với faster-whisper và không phải bộ đánh giá ASR y tế đầy đủ.",
            "",
            "## Tổng quan",
            "",
        ]
        for record in summary.get("split_records", []):
            lines.extend([
                f"### {record['split']}",
                f"- Số lỗi được phân loại: {record['error_count']}",
                "- Phân phối lỗi:",
            ])
            for error_type, count in record.get("error_distribution", {}).items():
                lines.append(f"  - {error_type}: {count}")
            lines.append("")

        lines.extend([
            "## Phân phối lỗi tổng hợp",
            "",
        ])
        for error_type, count in summary.get("error_distribution", {}).items():
            lines.append(f"- {error_type}: {count}")
        lines.append("")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
