import os
from typing import Any, Dict
import yaml

class AppConfig:
    """Application configuration loader for the evaluation pipeline."""
    
    def __init__(self, config_dir: str = "configs"):
        self.config_dir = config_dir
        self.dataset = self._load_yaml("dataset.yaml")
        self.taxonomy = self._load_yaml("taxonomy.yaml")
        self.llm = self._load_yaml("llm.yaml")
        self.asr = self._load_yaml("asr.yaml")
        self.report = self._load_yaml("report.yaml")
        self.external = self._load_yaml("external.yaml")
        
    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        filepath = os.path.join(self.config_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Configuration file not found: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                config = yaml.safe_load(f)
                return config or {}
            except yaml.YAMLError as e:
                raise ValueError(f"Error parsing YAML file {filepath}: {e}")

    def get_dataset_config(self) -> Dict[str, Any]:
        return self.dataset

    def get_taxonomy_config(self) -> Dict[str, Any]:
        return self.taxonomy

    def get_llm_config(self) -> Dict[str, Any]:
        return self.llm

    def get_asr_config(self) -> Dict[str, Any]:
        return self.asr

    def get_report_config(self) -> Dict[str, Any]:
        return self.report

    def get_external_config(self) -> Dict[str, Any]:
        return self.external
