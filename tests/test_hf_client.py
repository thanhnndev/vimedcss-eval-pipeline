import os
import json
from unittest.mock import MagicMock, patch
import pytest
from src.hf_client.download import HFDatasetClient

@pytest.fixture
def mock_config():
    return {
        "repo_id": "mock/ViMedCSS",
        "revision": "mock_rev",
        "local_raw_dir": "data/raw/vimedcss_mock"
    }

@patch("src.hf_client.download.HfApi")
def test_hf_client_get_repo_info(mock_api_class, mock_config):
    mock_api = MagicMock()
    mock_api_class.return_value = mock_api
    
    mock_dataset_info = MagicMock()
    mock_dataset_info.sha = "mock_commit_hash"
    mock_dataset_info.lastModified = None
    mock_dataset_info.private = False
    mock_api.dataset_info.return_value = mock_dataset_info

    client = HFDatasetClient(mock_config)
    info = client.get_repo_info()
    
    assert info["repo_id"] == "mock/ViMedCSS"
    assert info["revision"] == "mock_commit_hash"
    mock_api.dataset_info.assert_called_once_with(repo_id="mock/ViMedCSS", revision="mock_rev")

@patch("src.hf_client.download.HfApi")
def test_hf_client_list_files(mock_api_class, mock_config):
    mock_api = MagicMock()
    mock_api_class.return_value = mock_api
    mock_api.list_repo_files.return_value = ["file1.csv", "data/file2.parquet"]

    client = HFDatasetClient(mock_config)
    files = client.list_files()
    
    assert len(files) == 2
    assert "file1.csv" in files
    mock_api.list_repo_files.assert_called_once_with(repo_id="mock/ViMedCSS", repo_type="dataset", revision="mock_rev")

@patch("src.hf_client.download.hf_hub_download")
@patch("src.hf_client.download.HfApi")
def test_hf_client_download_metadata_only(mock_api_class, mock_download, mock_config, tmp_path):
    # Setup mocks
    mock_api = MagicMock()
    mock_api_class.return_value = mock_api
    
    mock_dataset_info = MagicMock()
    mock_dataset_info.sha = "mock_commit_hash"
    mock_api.dataset_info.return_value = mock_dataset_info
    
    mock_api.list_repo_files.return_value = [
        "ViMedCSS-Metadata/train_set.csv", 
        "data/train-00000.parquet"
    ]
    
    # Configure download client to use a temporary path for output manifest
    client = HFDatasetClient(mock_config)
    
    # Mock download file paths
    mock_download.return_value = str(tmp_path / "train_set.csv")
    
    # Create the mock file so os.path.getsize doesn't fail
    mock_file = tmp_path / "train_set.csv"
    mock_file.write_text("segment_id,segment_text\n1,Hello")
    
    # We patch the manifest and log paths so we don't pollute local directories
    with patch("builtins.open", create=True) as mock_open:
        manifest = client.download_metadata_only()
        
        # Verify that only the metadata file was downloaded, not parquet
        mock_download.assert_called_once_with(
            repo_id="mock/ViMedCSS",
            filename="ViMedCSS-Metadata/train_set.csv",
            repo_type="dataset",
            revision="mock_commit_hash",
            local_dir="data/raw/vimedcss_mock",
            local_dir_use_symlinks=False
        )
        
        assert manifest["repo_id"] == "mock/ViMedCSS"
        assert manifest["revision"] == "mock_commit_hash"
        assert len(manifest["files"]) == 1
        assert manifest["files"][0]["filename"] == "train_set.csv"
