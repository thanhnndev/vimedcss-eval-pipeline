import os
import json
import pandas as pd
import pytest
from src.audit.auditor import MetadataAuditor

@pytest.fixture
def sample_csv_content():
    return (
        "segment_id,duration_seconds,segment_text,cs_terms_list,topic,start_time,end_time\n"
        "Med_CS-100-1,10.5,Bệnh nhân dùng metformin điều trị,metformin,Treatments,01:10,01:20\n"
        "Med_CS-100-2,5.0,Xét nghiệm HbA1c và glucose,\"['HbA1c', 'glucose']\",Diagnostics,02:15,02:20\n"
        "Med_CS-100-3,6.2,Rỗng không có cs terms,,Nutrition,03:10,03:16\n"
        "Med_CS-100-1,8.0,Duplicate segment ID,insulin,Treatments,04:00,04:08\n"
        "Med_CS-100-4,,Transcript is missing,aspirin,Treatments,05:00,05:08\n"
    )

@pytest.fixture
def mock_config():
    return {
        "local_raw_dir": "data/raw/vimedcss_mock",
        "expected_fields": {
            "segment_id": "segment_id",
            "transcript": "segment_text",
            "cs_terms": "cs_terms_list",
            "topic": "topic",
            "duration": "duration_seconds",
            "start": "start_time",
            "end": "end_time"
        },
        "splits": ["train"]
    }

def test_metadata_auditor_schema_mapping(mock_config, tmp_path, sample_csv_content):
    # Save the sample CSV to tmp path
    csv_file = tmp_path / "train_set.csv"
    csv_file.write_text(sample_csv_content)
    
    mock_config["local_raw_dir"] = str(tmp_path)
    auditor = MetadataAuditor(mock_config)
    
    df, mapping = auditor.load_and_map_df(str(csv_file), "train")
    
    # Check mapping
    assert mapping["segment_id"] == "segment_id"
    assert mapping["transcript"] == "segment_text"
    assert mapping["cs_terms"] == "cs_terms_list"
    assert mapping["duration"] == "duration_seconds"
    
    # Check loaded clean dataframe
    assert len(df) == 5
    assert list(df["segment_id"]) == ["Med_CS-100-1", "Med_CS-100-2", "Med_CS-100-3", "Med_CS-100-1", "Med_CS-100-4"]
    assert list(df["split"]) == ["train"] * 5

def test_metadata_auditor_stats_and_issues(mock_config, tmp_path, sample_csv_content):
    csv_file = tmp_path / "train_set.csv"
    csv_file.write_text(sample_csv_content)
    
    mock_config["local_raw_dir"] = str(tmp_path)
    auditor = MetadataAuditor(mock_config)
    
    # Execute full audit
    # Patch output directories so we don't pollute local workspace outputs directory during tests
    out_dir = tmp_path / "outputs" / "audit"
    os.makedirs(out_dir, exist_ok=True)
    
    with pytest.MonkeyPatch.context() as mp:
        # We temporarily change working directory or mock save paths
        def mock_makedirs(*args, **kwargs):
            pass
            
        mp.setattr(os, "makedirs", mock_makedirs)
        
        # Manually invoke internals or let it run writing to tmp_path outputs
        df, _ = auditor.load_and_map_df(str(csv_file), "train")
        
        # Test stats computation
        stats = auditor._compute_local_stats(df)
        assert stats["total_rows"] == 5
        assert stats["duplicate_segment_id_count"] == 1 # "Med_CS-100-1" is duplicate
        assert stats["missing_transcript_count"] == 0 # "Transcript is missing" is string, not NaN/empty
        assert stats["missing_cs_terms_count"] == 1 # Med_CS-100-3 has empty cs_terms_list
        
        # Test split stats
        split_stats = auditor._compute_split_stats(df)
        assert len(split_stats) == 1
        assert split_stats.iloc[0]["row_count"] == 5
        # metformin (1) + HbA1c/glucose (2) + empty (0) + insulin (1) + aspirin (1) = 5 occurrences
        assert split_stats.iloc[0]["cs_term_occurrences"] == 5
        
        # Test quality issues detection
        issues = auditor._compute_quality_issues(df)
        assert len(issues) > 0
        issue_types = list(issues["issue_type"])
        assert "duplicate_segment_id" in issue_types
        assert "missing_cs_terms" in issue_types
