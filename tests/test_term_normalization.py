import os
import json
import pandas as pd
import pytest
from src.terms.extractor import clean_term, parse_terms, TermExtractor

def test_clean_term():
    # Lowercase & trimming
    assert clean_term("  Angiotensin  ") == "angiotensin"
    
    # Keep medical spellings
    assert clean_term("glutathion") == "glutathion"
    
    # Strip edge punctuation
    assert clean_term("[metformin]") == "metformin"
    assert clean_term("(glucose)") == "glucose"
    assert clean_term("insulin,") == "insulin"
    assert clean_term("-estrogen") == "estrogen"
    assert clean_term("estrogen-") == "estrogen"
    
    # Protect abbreviation structures, spaces, and internal dots/slashes/numbers
    assert clean_term("HbA1c") == "hba1c"
    assert clean_term("T3") == "t3"
    assert clean_term("E. coli") == "e. coli"
    assert clean_term("T3/T4") == "t3/t4"
    assert clean_term("co-enzyme") == "co-enzyme"
    assert clean_term("Sjögren") == "sjögren"

def test_parse_terms():
    # Empty/NaN values
    assert parse_terms(None) == []
    assert parse_terms(pd.NA) == []
    assert parse_terms("") == []
    assert parse_terms("   ") == []
    
    # Single term
    assert parse_terms("metformin") == ["metformin"]
    
    # Semicolon separated list
    assert parse_terms("hormone; estrogen") == ["hormone", "estrogen"]
    assert parse_terms("uric; urat; purin") == ["uric", "urat", "purin"]
    
    # Comma separated list
    assert parse_terms("lipid, insulin") == ["lipid", "insulin"]
    
    # JSON array with double quotes
    assert parse_terms('["lipid", "estrogen"]') == ["lipid", "estrogen"]
    
    # JSON array with single quotes (which is converted and parsed)
    assert parse_terms("['HbA1c', 'glucose']") == ["HbA1c", "glucose"]
    
    # Broken JSON format fallback split
    assert parse_terms("['HbA1c'; 'glucose']") == ["HbA1c", "glucose"]
    
    # Already a list or tuple
    assert parse_terms(["lipid", "estrogen"]) == ["lipid", "estrogen"]
    assert parse_terms(("lipid", "estrogen")) == ["lipid", "estrogen"]

@pytest.fixture
def mock_dataset_and_taxonomy(tmp_path):
    # Create mock metadata CSV files for train, test, and hard splits
    # train_set.csv
    train_content = (
        "segment_id,duration_seconds,segment_text,cs_terms_list,topic,start_time,end_time\n"
        "seg_tr_1,10.0,Sample train 1,\"metformin; insulin\",Treatments,00:00,00:10\n"
        "seg_tr_2,5.0,Sample train 2,\"HbA1c; glucose\",Diagnostics,00:10,00:15\n"
        "seg_tr_3,8.0,Sample train 3,\"metformin\",Treatments,00:15,00:23\n"
    )
    # test_set.csv
    test_content = (
        "segment_id,duration_seconds,segment_text,cs_terms_list,Topic,start_time,end_time\n"
        "seg_te_1,7.0,Sample test 1,\"metformin\",Treatments,00:00,00:07\n"
        "seg_te_2,6.0,Sample test 2,\"estrogen\",Treatments,00:07,00:13\n"
    )
    # hard_set.csv
    hard_content = (
        "segment_id,duration_seconds,segment_text,cs_terms_list,topic,start_time,end_time\n"
        "seg_hd_1,5.0,Sample hard 1,\"metformin\",Treatments,00:00,00:05\n"
        "seg_hd_2,12.0,Sample hard 2,\"leptin; hormone\",Treatments,00:05,00:17\n"
    )
    
    os.makedirs(tmp_path / "ViMedCSS-Metadata", exist_ok=True)
    (tmp_path / "ViMedCSS-Metadata" / "train_set.csv").write_text(train_content)
    (tmp_path / "ViMedCSS-Metadata" / "test_set.csv").write_text(test_content)
    (tmp_path / "ViMedCSS-Metadata" / "hard_set.csv").write_text(hard_content)
    
    dataset_config = {
        "local_raw_dir": str(tmp_path),
        "expected_fields": {
            "segment_id": "segment_id",
            "transcript": "segment_text",
            "cs_terms": "cs_terms_list",
            "topic": "topic",
            "duration": "duration_seconds",
            "start": "start_time",
            "end": "end_time"
        },
        "splits": ["train", "test", "hard"]
    }
    
    taxonomy_config = {
        "frequency_buckets": {
            "singleton": [1, 1],
            "rare": [2, 3],
            "common": [4, None]
        }
    }
    
    return dataset_config, taxonomy_config

def test_term_extractor_pipeline(mock_dataset_and_taxonomy, tmp_path):
    dataset_config, taxonomy_config = mock_dataset_and_taxonomy
    
    extractor = TermExtractor(dataset_config, taxonomy_config)
    # Patch output directory so it writes inside tmp_path
    extractor.output_dir = str(tmp_path / "outputs" / "term_coverage")
    
    stats = extractor.extract_and_analyze()
    
    # Assert return statistics
    assert stats["total_raw_term_occurrences"] == 10
    # unique terms: metformin (4), insulin (1), hba1c (1), glucose (1), estrogen (1), leptin (1), hormone (1) = 7
    assert stats["total_unique_normalized_terms"] == 7
    # common terms (>=4 occurrences): metformin (4) = 1
    assert stats["common_terms_count"] == 1
    
    # Assert generated files exist
    assert os.path.exists(os.path.join(extractor.output_dir, "cs_terms_inventory.csv"))
    assert os.path.exists(os.path.join(extractor.output_dir, "cs_term_examples.jsonl"))
    assert os.path.exists(os.path.join(extractor.output_dir, "cs_terms_by_split.csv"))
    assert os.path.exists(os.path.join(extractor.output_dir, "cs_terms_by_topic.csv"))
    assert os.path.exists(os.path.join(extractor.output_dir, "rare_terms.csv"))
    assert os.path.exists(os.path.join(extractor.output_dir, "common_terms.csv"))
    assert os.path.exists(os.path.join(extractor.output_dir, "hard_only_terms.csv"))
    assert os.path.exists(os.path.join(extractor.output_dir, "train_seen_hard_terms.csv"))
    assert os.path.exists(os.path.join(extractor.output_dir, "unseen_in_train_terms.csv"))
    
    # Verify inventory content
    inv_df = pd.read_csv(os.path.join(extractor.output_dir, "cs_terms_inventory.csv"))
    # Check column names
    expected_cols = [
        "normalized_term", "raw_forms", "occurrence_count", "utterance_count",
        "splits_present", "topics_present", "example_segment_ids", "example_texts",
        "entity_category", "medical_domain", "specialty", "is_code_switch_term",
        "is_abbreviation", "is_common_term", "frequency_bucket", "classification_source",
        "classification_confidence", "needs_human_review", "notes"
    ]
    for col in expected_cols:
        assert col in inv_df.columns
        
    # Check that metformin has occurrence_count = 4 and is_common_term = True
    metformin_row = inv_df[inv_df["normalized_term"] == "metformin"].iloc[0]
    assert metformin_row["occurrence_count"] == 4
    assert bool(metformin_row["is_common_term"]) is True
    assert metformin_row["frequency_bucket"] == "common"
    
    # Check HbA1c is classified as abbreviation
    hba1c_row = inv_df[inv_df["normalized_term"] == "hba1c"].iloc[0]
    assert bool(hba1c_row["is_abbreviation"]) is True
    
    # Check train_seen_hard_terms.csv contains metformin
    seen_hard_df = pd.read_csv(os.path.join(extractor.output_dir, "train_seen_hard_terms.csv"))
    assert "metformin" in list(seen_hard_df["normalized_term"])
    
    # Check unseen_in_train_terms.csv contains estrogen, leptin, hormone
    unseen_df = pd.read_csv(os.path.join(extractor.output_dir, "unseen_in_train_terms.csv"))
    unseen_terms = list(unseen_df["normalized_term"])
    assert "estrogen" in unseen_terms
    assert "leptin" in unseen_terms
    assert "hormone" in unseen_terms
    assert "metformin" not in unseen_terms
