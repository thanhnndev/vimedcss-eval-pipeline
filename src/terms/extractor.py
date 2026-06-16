import os
import json
import re
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Set, Tuple
from src.shared.logging import setup_logger
from src.audit.auditor import MetadataAuditor

logger = setup_logger("extractor")

def clean_term(term: str) -> str:
    """Cleans a raw medical term by lowercasing, trimming, and stripping edge punctuation.
    
    Protects internal structures like medical abbreviations, numbers, and slashes/dots
    (e.g., 'HbA1c' -> 'hba1c', 'E. coli' -> 'e. coli', '[metformin]' -> 'metformin').
    """
    if not isinstance(term, str):
        return ""
    # Trim whitespace
    term = term.strip()
    # Lowercase
    term = term.lower()
    # Strip leading/trailing non-alphanumeric/non-space/non-underscore characters
    # e.g., punctuation like brackets, parentheses, quotes, commas, periods, semicolons
    term = re.sub(r'^[^\w\d\s]+|[^\w\d\s]+$', '', term, flags=re.UNICODE)
    return term.strip()

def parse_terms(terms_val: Any) -> List[str]:
    """Parses cs_terms_list field in various formats (JSON lists, comma strings, semicolon strings)."""
    if terms_val is None:
        return []
    
    if isinstance(terms_val, (list, tuple, np.ndarray)):
        raw_list = [str(item) for item in terms_val if pd.notna(item)]
    else:
        try:
            if pd.isna(terms_val):
                return []
        except ValueError:
            pass
            
        if isinstance(terms_val, str):
            terms_str = terms_val.strip()
            if not terms_str:
                return []
            
            # Check if it looks like a JSON list
            if terms_str.startswith("[") and terms_str.endswith("]"):
                try:
                    # Replace single quotes with double quotes for valid JSON parsing
                    normalized_json = terms_str.replace("'", '"')
                    parsed = json.loads(normalized_json)
                    if isinstance(parsed, list):
                        raw_list = [str(item) for item in parsed]
                    else:
                        raw_list = [str(parsed)]
                except Exception:
                    # Fallback: strip brackets and split by semicolon or comma
                    stripped = terms_str[1:-1]
                    if ";" in stripped:
                        raw_list = stripped.split(";")
                    else:
                        raw_list = stripped.split(",")
            elif ";" in terms_str:
                raw_list = terms_str.split(";")
            elif "," in terms_str:
                raw_list = terms_str.split(",")
            else:
                raw_list = [terms_str]
        else:
            raw_list = [str(terms_val)]
        
    return [item.strip().strip("'\"") for item in raw_list if item.strip().strip("'\"")]

class TermExtractor:
    """Extracts, normalizes, and counts code-switching terms from ViMedCSS metadata."""
    
    def __init__(self, dataset_config: Dict[str, Any], taxonomy_config: Dict[str, Any]):
        self.dataset_config = dataset_config
        self.taxonomy_config = taxonomy_config
        self.auditor = MetadataAuditor(dataset_config)
        self.output_dir = "outputs/term_coverage"
        
    def extract_and_analyze(self) -> Dict[str, Any]:
        """Loads splits, extracts and normalizes terms, aggregates stats, and exports files."""
        os.makedirs(self.output_dir, exist_ok=True)
        
        all_dfs = []
        for split in self.auditor.splits:
            try:
                filepath = self.auditor._resolve_file_path(split)
                df, _ = self.auditor.load_and_map_df(filepath, split)
                all_dfs.append(df)
            except Exception as e:
                logger.error(f"Failed to load split '{split}': {e}")
                raise
                
        if not all_dfs:
            raise ValueError("No splits were loaded successfully.")
            
        merged_df = pd.concat(all_dfs, ignore_index=True)
        logger.info(f"Loaded {len(merged_df)} total rows across splits for term extraction.")
        
        # We will collect term occurrence examples and aggregate inventory stats
        term_occurrences: List[Dict[str, Any]] = []
        
        # Setup aggregation dictionaries for inventory
        # key: normalized_term
        raw_forms_dict: Dict[str, Set[str]] = {}
        counts_dict: Dict[str, int] = {}
        utterances_dict: Dict[str, Set[str]] = {} # set of segment_ids
        splits_dict: Dict[str, Set[str]] = {}
        topics_dict: Dict[str, Set[str]] = {}
        examples_dict: Dict[str, List[Tuple[str, str]]] = {} # List of (segment_id, transcript)
        
        for _, row in merged_df.iterrows():
            seg_id = str(row["segment_id"])
            transcript = str(row["transcript"]) if pd.notna(row["transcript"]) else ""
            cs_terms_raw_val = row["cs_terms"]
            split = str(row["split"])
            topic = str(row["topic"]) if pd.notna(row["topic"]) else "unknown"
            
            raw_terms = parse_terms(cs_terms_raw_val)
            
            for raw_term in raw_terms:
                norm_term = clean_term(raw_term)
                if not norm_term:
                    continue
                    
                # Store occurrence
                term_occurrences.append({
                    "segment_id": seg_id,
                    "raw_form": raw_term,
                    "normalized_term": norm_term,
                    "split": split,
                    "topic": topic,
                    "transcript": transcript
                })
                
                # Aggregate for inventory
                if norm_term not in counts_dict:
                    raw_forms_dict[norm_term] = set()
                    counts_dict[norm_term] = 0
                    utterances_dict[norm_term] = set()
                    splits_dict[norm_term] = set()
                    topics_dict[norm_term] = set()
                    examples_dict[norm_term] = []
                    
                raw_forms_dict[norm_term].add(raw_term)
                counts_dict[norm_term] += 1
                utterances_dict[norm_term].add(seg_id)
                splits_dict[norm_term].add(split)
                topics_dict[norm_term].add(topic)
                
                # Keep up to 5 examples to avoid bloat in the CSV
                if len(examples_dict[norm_term]) < 5:
                    examples_dict[norm_term].append((seg_id, transcript))
                    
        # Write term examples JSONL
        examples_jsonl_path = os.path.join(self.output_dir, "cs_term_examples.jsonl")
        with open(examples_jsonl_path, "w", encoding="utf-8") as f:
            for occ in term_occurrences:
                f.write(json.dumps(occ, ensure_ascii=False) + "\n")
        logger.info(f"Saved CS term examples map to {examples_jsonl_path}")
        
        # Write raw term occurrences CSV
        raw_csv_path = os.path.join(self.output_dir, "cs_terms_raw.csv")
        raw_occ_df = pd.DataFrame([
            {
                "segment_id": occ["segment_id"],
                "raw_term": occ["raw_form"],
                "normalized_term": occ["normalized_term"],
                "split": occ["split"],
                "topic": occ["topic"],
                "transcript": occ["transcript"]
            } for occ in term_occurrences
        ])
        raw_occ_df.to_csv(raw_csv_path, index=False)
        
        # Write normalized term occurrences CSV
        normalized_csv_path = os.path.join(self.output_dir, "cs_terms_normalized.csv")
        norm_occ_df = pd.DataFrame(term_occurrences)
        norm_occ_df.to_csv(normalized_csv_path, index=False)
        
        # Build inventory
        inventory_items: List[Dict[str, Any]] = []
        buckets_config = self.taxonomy_config.get("frequency_buckets", {
            "singleton": [1, 1],
            "rare": [2, 4],
            "medium": [5, 19],
            "common": [20, None]
        })
        
        for term, count in counts_dict.items():
            raw_forms_set = raw_forms_dict[term]
            splits_present = sorted(list(splits_dict[term]))
            topics_present = sorted(list(topics_dict[term]))
            
            # Heuristic for is_abbreviation
            is_abbrev = False
            if any(c.isdigit() for c in term):
                is_abbrev = True
            elif any(raw.isupper() and len(raw) >= 2 for raw in raw_forms_set):
                is_abbrev = True
                
            freq_bucket = self._get_frequency_bucket(count, buckets_config)
            is_common = freq_bucket == "common"
            
            ex_seg_ids = ";".join([ex[0] for ex in examples_dict[term]])
            # Escape semicolons in example texts
            ex_texts = ";".join([ex[1].replace(";", ",") for ex in examples_dict[term]])
            
            inventory_items.append({
                "normalized_term": term,
                "raw_forms": ";".join(sorted(list(raw_forms_set))),
                "occurrence_count": count,
                "utterance_count": len(utterances_dict[term]),
                "splits_present": ";".join(splits_present),
                "topics_present": ";".join(topics_present),
                "example_segment_ids": ex_seg_ids,
                "example_texts": ex_texts,
                "entity_category": "unknown", # placeholder for Phase 2
                "medical_domain": "unknown",  # placeholder for Phase 2
                "specialty": "unknown",       # placeholder for Phase 2
                "is_code_switch_term": True,  # by definition of being in cs_terms_list
                "is_abbreviation": is_abbrev,
                "is_common_term": is_common,
                "frequency_bucket": freq_bucket,
                "classification_source": "none",
                "classification_confidence": 0.0,
                "needs_human_review": False,
                "notes": ""
            })
            
        inventory_df = pd.DataFrame(inventory_items)
        # Sort inventory by occurrence_count descending, then normalized_term ascending
        if not inventory_df.empty:
            inventory_df = inventory_df.sort_values(
                by=["occurrence_count", "normalized_term"],
                ascending=[False, True]
            )
            
        inventory_csv_path = os.path.join(self.output_dir, "cs_terms_inventory.csv")
        inventory_df.to_csv(inventory_csv_path, index=False)
        logger.info(f"Saved CS terms inventory to {inventory_csv_path}")
        
        # 1. Distribution by split: cs_terms_by_split.csv
        split_dist = []
        for term, s_set in splits_dict.items():
            for split in s_set:
                # Count occurrences of term in this split
                s_count = sum(1 for occ in term_occurrences if occ["normalized_term"] == term and occ["split"] == split)
                split_dist.append({
                    "normalized_term": term,
                    "split": split,
                    "occurrence_count": s_count
                })
        split_dist_df = pd.DataFrame(split_dist)
        if not split_dist_df.empty:
            split_dist_df = split_dist_df.sort_values(by=["occurrence_count", "normalized_term"], ascending=[False, True])
        split_dist_df.to_csv(os.path.join(self.output_dir, "cs_terms_by_split.csv"), index=False)
        
        # 2. Distribution by topic: cs_terms_by_topic.csv
        topic_dist = []
        for term, t_set in topics_dict.items():
            for topic in t_set:
                t_count = sum(1 for occ in term_occurrences if occ["normalized_term"] == term and occ["topic"] == topic)
                topic_dist.append({
                    "normalized_term": term,
                    "topic": topic,
                    "occurrence_count": t_count
                })
        topic_dist_df = pd.DataFrame(topic_dist)
        if not topic_dist_df.empty:
            topic_dist_df = topic_dist_df.sort_values(by=["occurrence_count", "normalized_term"], ascending=[False, True])
        topic_dist_df.to_csv(os.path.join(self.output_dir, "cs_terms_by_topic.csv"), index=False)
        
        # 3. Rare terms: rare_terms.csv (frequency bucket rare or singleton)
        rare_df = inventory_df[inventory_df["frequency_bucket"].isin(["rare", "singleton"])]
        rare_df.to_csv(os.path.join(self.output_dir, "rare_terms.csv"), index=False)
        
        # 4. Common terms: common_terms.csv
        common_df = inventory_df[inventory_df["frequency_bucket"] == "common"]
        common_df.to_csv(os.path.join(self.output_dir, "common_terms.csv"), index=False)
        
        # 5. Split overlap analysis
        # Find splits sets per term
        train_terms = set(inventory_df[inventory_df["splits_present"].str.contains("train")]["normalized_term"])
        validation_terms = set(inventory_df[inventory_df["splits_present"].str.contains("validation")]["normalized_term"])
        test_terms = set(inventory_df[inventory_df["splits_present"].str.contains("test")]["normalized_term"])
        hard_terms = set(inventory_df[inventory_df["splits_present"].str.contains("hard")]["normalized_term"])
        
        # Terms only in hard split
        hard_only = hard_terms - (train_terms | validation_terms | test_terms)
        hard_only_df = inventory_df[inventory_df["normalized_term"].isin(hard_only)]
        hard_only_df.to_csv(os.path.join(self.output_dir, "hard_only_terms.csv"), index=False)
        
        # Hard terms seen in train
        train_seen_hard = hard_terms & train_terms
        train_seen_hard_df = inventory_df[inventory_df["normalized_term"].isin(train_seen_hard)]
        train_seen_hard_df.to_csv(os.path.join(self.output_dir, "train_seen_hard_terms.csv"), index=False)
        
        # Unseen in train: terms in eval splits (validation, test, hard) but NOT in train
        eval_terms = validation_terms | test_terms | hard_terms
        unseen_in_train = eval_terms - train_terms
        unseen_in_train_df = inventory_df[inventory_df["normalized_term"].isin(unseen_in_train)]
        unseen_in_train_df.to_csv(os.path.join(self.output_dir, "unseen_in_train_terms.csv"), index=False)
        
        # Compute brief stats for return value
        stats = {
            "total_raw_term_occurrences": len(term_occurrences),
            "total_unique_normalized_terms": len(inventory_df),
            "common_terms_count": len(common_df),
            "rare_terms_count": len(rare_df),
            "hard_only_terms_count": len(hard_only_df),
            "train_seen_hard_terms_count": len(train_seen_hard_df),
            "unseen_in_train_terms_count": len(unseen_in_train_df)
        }
        
        logger.info("CS term extraction and normalization completed successfully!")
        return stats
        
    def _get_frequency_bucket(self, count: int, buckets_config: Dict[str, Any]) -> str:
        for bucket_name, limits in buckets_config.items():
            min_val = limits[0]
            max_val = limits[1]
            if max_val is None:
                if count >= min_val:
                    return bucket_name
            else:
                if min_val <= count <= max_val:
                    return bucket_name
        return "unknown"
