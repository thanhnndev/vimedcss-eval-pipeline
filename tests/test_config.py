import os
import pytest
from src.shared.config import AppConfig

def test_app_config_loading():
    """Verify that AppConfig correctly loads all configuration files."""
    config = AppConfig()
    
    # Verify dataset config
    dataset = config.get_dataset_config()
    assert dataset is not None
    assert dataset.get("repo_id") == "tensorxt/ViMedCSS"
    assert "splits" in dataset
    
    # Verify taxonomy config
    taxonomy = config.get_taxonomy_config()
    assert taxonomy is not None
    assert "frequency_buckets" in taxonomy
    
    # Verify llm config
    llm = config.get_llm_config()
    assert llm is not None
    assert llm.get("provider") == "openai"
    
    # Verify asr config
    asr = config.get_asr_config()
    assert asr is not None
    assert asr.get("enabled") is True
    
    # Verify report config
    report = config.get_report_config()
    assert report is not None
    assert report.get("language") == "vi"

def test_missing_config_raises_error():
    """Verify that initializing AppConfig with non-existent dir raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        AppConfig(config_dir="non_existent_configs")
