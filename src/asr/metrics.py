import os
import csv
import logging
from typing import Any, Dict, List, Optional

import pandas as pd
import jiwer

from src.shared.logging import setup_logger
from src.shared.config import AppConfig
from src.terms.extractor import clean_term

logger = setup_logger("asr.metrics")


class ASRMetrics:
    """Computes WER/CER and CS-term recall metrics from ASR hypotheses."""

    def __init__(self, dataset_config: Dict[str, Any], asr_config: Dict[str, Any], taxonomy_config: Dict[str, Any]):
        self.dataset_config = dataset_config
        self.asr_config = asr_config
        self.taxonomy_config = taxonomy_config
        self.output_dir = asr_config.get("output_dir", "outputs/asr_eval")
        self.errors_dir = os.path.join(self.output_dir, "errors")
        os.makedirs(self.errors_dir, exist_ok=True)

    def compute_and_write(self, mock: bool = False, limit: Optional[int] = None) -> Dict[str, Any]:
        """Load hypotheses, compute metrics per split, and write CSV outputs."""
        splits = self.asr_config.get("splits", ["test", "hard"])
        inventory = self._load_inventory()
        rows: List[Dict[str, Any]] = []

        for split in splits:
            hyp_path = os.path.join(self.output_dir, f"hypotheses_{split}.jsonl")
            if not os.path.exists(hyp_path):
                logger.warning(f"Missing hypotheses file for {split}: {hyp_path}")
                continue
            data = self._load_jsonl(hyp_path)
            if limit is not None and limit > 0:
                data = data[:limit]
            if not data:
                logger.info(f"Empty hypotheses for {split}; writing zero-stats row")
                rows.append(self._empty_metrics_row(split, 0))
                continue

            ref_lookup = self._load_reference_lookup(split)
            wer_vals, cer_vals = [], []
            term_scores: List[Dict[str, Any]] = []

            for item in data:
                reference = ref_lookup.get(item.get("segment_id", ""), "")
                hypothesis = item.get("hypothesis_text", "")
                if reference or hypothesis:
                    wer_vals.append(jiwer.wer(reference, hypothesis))
                    cer_vals.append(jiwer.cer(reference, hypothesis))
                term_scores.append(self._score_terms(reference, hypothesis, inventory))

            recall_vals = [score["recall"] for score in term_scores]
            missing_vals = [score["missing_rate"] for score in term_scores]
            sub_vals = [score["substitution_rate"] for score in term_scores]

            rows.append({
                "split": split,
                "segment_count": len(data),
                "wer": sum(wer_vals) / len(wer_vals) if wer_vals else 0.0,
                "cer": sum(cer_vals) / len(cer_vals) if cer_vals else 0.0,
                "cs_term_recall": sum(recall_vals) / len(recall_vals) if recall_vals else 0.0,
                "cs_term_missing_rate": sum(missing_vals) / len(missing_vals) if missing_vals else 0.0,
                "cs_term_substitution_rate": sum(sub_vals) / len(sub_vals) if sub_vals else 0.0,
            })

        metrics_path = os.path.join(self.output_dir, "metrics_summary.csv")
        pd.DataFrame(rows).to_csv(metrics_path, index=False)
        logger.info(f"Wrote metrics summary to {metrics_path}")

        if not mock:
            top_terms = self._compute_top_failed_terms(splits, inventory)
            top_terms_path = os.path.join(self.errors_dir, "top_failed_terms.csv")
            pd.DataFrame(top_terms).to_csv(top_terms_path, index=False)
            logger.info(f"Wrote top failed terms to {top_terms_path}")

        return {"splits": len(rows)}

    def _load_inventory(self) -> pd.DataFrame:
        path = os.path.join("outputs", "term_coverage", "cs_terms_inventory.csv")
        if not os.path.exists(path):
            raise FileNotFoundError(f"CS term inventory not found: {path}")
        df = pd.read_csv(path)
        df["normalized_term"] = df["normalized_term"].astype(str).apply(clean_term)
        return df

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

    def _score_terms(self, reference: str, hypothesis: str, inventory: pd.DataFrame) -> Dict[str, Any]:
        terms = [str(t).strip() for t in str(reference).split(";") if str(t).strip()]
        if not terms:
            return {"recall": 0.0, "missing_rate": 0.0, "substitution_rate": 0.0}

        norm_ref_terms = [clean_term(t) for t in terms]
        norm_ref_terms = [t for t in norm_ref_terms if t]
        norm_hyp = clean_term(hypothesis)

        if not norm_ref_terms:
            return {"recall": 0.0, "missing_rate": 0.0, "substitution_rate": 0.0}

        matched = sum(1 for t in norm_ref_terms if t in norm_hyp)
        recall = matched / len(norm_ref_terms)
        missing = 1.0 - recall
        substitution = 0.0 if recall >= 1.0 else missing

        return {"recall": recall, "missing_rate": missing, "substitution_rate": substitution}

    def _compute_top_failed_terms(self, splits: List[str], inventory: pd.DataFrame) -> List[Dict[str, Any]]:
        term_stats: Dict[str, Dict[str, Any]] = {}
        for term, row in inventory.iterrows():
            norm = str(inventory.loc[term, "normalized_term"])
            term_stats[norm] = {
                "normalized_term": norm,
                "total_occurrences": int(inventory.loc[term, "occurrence_count"]) if "occurrence_count" in inventory.columns else 0,
                "entity_category": inventory.loc[term, "entity_category"] if "entity_category" in inventory.columns else "unknown",
                "medical_domain": inventory.loc[term, "medical_domain"] if "medical_domain" in inventory.columns else "unknown",
                "recall_count": 0,
            }

        for split in splits:
            hyp_path = os.path.join(self.output_dir, f"hypotheses_{split}.jsonl")
            if not os.path.exists(hyp_path):
                continue
            ref_lookup = self._load_reference_lookup(split)
            data = self._load_jsonl(hyp_path)
            for item in data:
                reference = ref_lookup.get(item.get("segment_id", ""), "")
                hypothesis = item.get("hypothesis_text", "")
                norm_hyp = clean_term(hypothesis)
                terms = [clean_term(t) for t in str(reference).split(";") if str(t).strip()]
                for term in terms:
                    if not term:
                        continue
                    if term in term_stats:
                        term_stats[term]["recall_count"] += 1 if term in norm_hyp else 0

        scored = []
        for stats in term_stats.values():
            total = stats["total_occurrences"]
            recall = stats["recall_count"] / total if total else 0.0
            scored.append({
                "term": stats["normalized_term"],
                "normalized_term": stats["normalized_term"],
                "total_occurrences": total,
                "recall_count": stats["recall_count"],
                "recall_rate": recall,
                "entity_category": stats["entity_category"],
                "medical_domain": stats["medical_domain"],
            })

        scored.sort(key=lambda x: x["recall_rate"])
        return scored[:50]

    def _empty_metrics_row(self, split: str, segment_count: int) -> Dict[str, Any]:
        return {
            "split": split,
            "segment_count": segment_count,
            "wer": 0.0,
            "cer": 0.0,
            "cs_term_recall": 0.0,
            "cs_term_missing_rate": 0.0,
            "cs_term_substitution_rate": 0.0,
        }

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
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning(f"Skipping invalid JSONL line in {path}")
        return rows
