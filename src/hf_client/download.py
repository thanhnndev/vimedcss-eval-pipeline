import os
import json
import datetime
from typing import List, Dict, Any, Optional
from huggingface_hub import HfApi, hf_hub_download
from src.shared.logging import setup_logger

logger = setup_logger("hf-client")

class HFDatasetClient:
    """Client for interacting with Hugging Face dataset repositories."""
    
    def __init__(self, config: Dict[str, Any]):
        self.repo_id = config.get("repo_id", "tensorxt/ViMedCSS")
        self.revision = config.get("revision")
        self.local_raw_dir = config.get("local_raw_dir", "data/raw/vimedcss")
        self.api = HfApi()

    def get_repo_info(self) -> Dict[str, Any]:
        """Fetches metadata about the repository, including current commit hash."""
        try:
            info = self.api.dataset_info(repo_id=self.repo_id, revision=self.revision)
            return {
                "repo_id": self.repo_id,
                "revision": info.sha,
                "last_modified": info.lastModified.isoformat() if info.lastModified else None,
                "private": info.private,
            }
        except Exception as e:
            logger.error(f"Failed to fetch dataset info for {self.repo_id}: {e}")
            raise

    def list_files(self) -> List[str]:
        """Lists all files in the repository."""
        try:
            files = self.api.list_repo_files(repo_id=self.repo_id, repo_type="dataset", revision=self.revision)
            logger.info(f"Found {len(files)} files in repository {self.repo_id}")
            return files
        except Exception as e:
            logger.error(f"Failed to list files in repository {self.repo_id}: {e}")
            raise

    def download_metadata_only(self) -> Dict[str, Any]:
        """Downloads only the metadata CSV files from the repository."""
        os.makedirs(self.local_raw_dir, exist_ok=True)
        os.makedirs("outputs/audit", exist_ok=True)
        
        repo_info = self.get_repo_info()
        commit_hash = repo_info["revision"]
        
        all_files = self.list_files()
        # Filter files: must be CSV files in the metadata folder
        metadata_files = [f for f in all_files if f.endswith(".csv") and "Metadata" in f]
        
        if not metadata_files:
            # Fallback to any CSV file in the repo
            metadata_files = [f for f in all_files if f.endswith(".csv")]
            
        logger.info(f"Targeting {len(metadata_files)} metadata files for download: {metadata_files}")
        
        manifest_files = []
        download_logs = []
        
        for filepath in metadata_files:
            filename = os.path.basename(filepath)
            local_path = os.path.join(self.local_raw_dir, filename)
            
            log_entry = {
                "file": filepath,
                "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "status": "pending"
            }
            
            try:
                logger.info(f"Downloading {filepath} to {local_path} ...")
                downloaded_file = hf_hub_download(
                    repo_id=self.repo_id,
                    filename=filepath,
                    repo_type="dataset",
                    revision=commit_hash,
                    local_dir=self.local_raw_dir,
                    local_dir_use_symlinks=False
                )
                
                # Relocate to standardized name/location if snapshot downloaded to a nested path
                # hf_hub_download local_dir will put it under the original relative path inside local_raw_dir
                # e.g., local_raw_dir/ViMedCSS-Metadata/valid_set.csv. Let's trace where it was actually saved.
                actual_path = os.path.abspath(downloaded_file)
                size_bytes = os.path.getsize(actual_path)
                
                log_entry["status"] = "success"
                log_entry["completed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                log_entry["size_bytes"] = size_bytes
                log_entry["local_path"] = actual_path
                
                manifest_files.append({
                    "filename": filename,
                    "rel_path": filepath,
                    "size_bytes": size_bytes,
                    "local_path": actual_path,
                    "downloaded_at": log_entry["completed_at"]
                })
                logger.info(f"Successfully downloaded {filename} ({size_bytes} bytes)")
                
            except Exception as e:
                logger.error(f"Failed to download {filepath}: {e}")
                log_entry["status"] = "failed"
                log_entry["error"] = str(e)
                log_entry["completed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                raise e
            finally:
                download_logs.append(log_entry)

        # Write manifest file
        manifest = {
            "repo_id": self.repo_id,
            "revision": commit_hash,
            "downloaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "files": manifest_files
        }
        
        manifest_path = "outputs/audit/hf_file_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
            
        # Write download logs
        log_path = "outputs/audit/download_log.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            for entry in download_logs:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                
        logger.info(f"Acquisition manifest saved to {manifest_path}")
        return manifest
