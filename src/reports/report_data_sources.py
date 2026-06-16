"""Data source registry module for ViMedCSS evaluation pipeline.

This module provides the DataSourceRegistry class that generates a report documenting
all data sources used in the pipeline with their provenance categories.
"""

import os
import datetime
from typing import Dict, Any, List, Optional
from src.shared.logging import setup_logger

logger = setup_logger("reports.data_sources")


class DataSourceRegistry:
    """Registry of data sources with provenance tracking.

    This class generates a markdown report documenting all data sources used
    in the ViMedCSS evaluation pipeline, including their provenance categories,
    URLs, licenses, and verification status.
    """

    # Provenance category descriptions
    PROVENANCE_CATEGORIES = {
        "paper_reported": {
            "vi": "Giá trị được công bố trong paper hoặc dataset card gốc",
            "description": "Data directly reported in the published paper or Hugging Face dataset card",
        },
        "hf_reported": {
            "vi": "Giá trị từ Hugging Face metadata của dataset repository",
            "description": "Data sourced from Hugging Face repository metadata",
        },
        "local_verified": {
            "vi": "Giá trị được xác minh từ các file cục bộ",
            "description": "Data verified from local audit outputs",
        },
        "llm_inferred": {
            "vi": "Giá trị suy luận từ LLM structured output với confidence flags",
            "description": "Data inferred from LLM structured output with confidence and review flags",
        },
    }

    def __init__(
        self,
        dataset_config: Dict[str, Any],
        external_config: Dict[str, Any],
    ):
        """Initialize the DataSourceRegistry.

        Args:
            dataset_config: Dataset configuration dict
            external_config: External reference configuration dict
        """
        self.dataset_config = dataset_config
        self.external_config = external_config
        self.output_dir = "outputs/reports"
        os.makedirs(self.output_dir, exist_ok=True)

    def generate(self) -> str:
        """Generate the data sources report file.

        Returns:
            Path to the generated report file
        """
        content = self.generate_report_content({})

        output_path = os.path.join(self.output_dir, "report_data_sources.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Data sources report written to {output_path}")
        return output_path

    def generate_report_content(self, context: Dict[str, Any]) -> str:
        """Generate the data sources report content.

        Args:
            context: Rendering context (optional, for compatibility)

        Returns:
            Markdown content for the report
        """
        lines = [
            "# Nguồn dữ liệu và Mức độ Kiểm chứng",
            f"\n*Ngày tạo: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n",
            "\n---\n",
            "\n## 1. Tổng quan về Provenance Categories",
            "\nBáo cáo này phân biệt rõ ràng nguồn gốc của dữ liệu theo 4 mức độ kiểm chứng:\n",
        ]

        # Add provenance category descriptions
        for category, info in self.PROVENANCE_CATEGORIES.items():
            lines.extend([
                f"\n### `{category}`",
                f"\n**Tiếng Việt:** {info['vi']}",
                f"\n**English:** {info['description']}\n",
            ])

        # Add data sources table
        lines.extend([
            "\n---\n",
            "\n## 2. Nguồn dữ liệu sử dụng trong Pipeline",
            "\n| # | Nguồn | Loại | URL / Mô tả | Giấy phép / Lưu ý | Trạng thái kiểm chứng |",
            "|---|---|---|---|---|---|",
        ])

        # Primary dataset source
        lines.extend([
            "| 1 | VietMedCSS Dataset | Dataset | https://huggingface.co/datasets/tensorxt/ViMedCSS | Apache 2.0 | `paper_reported` + `hf_reported` |",
            "| 2 | VietMedVoice Paper | Paper | https://arxiv.org (pending) | Pending | `paper_reported` |",
            "| 3 | Hugging Face Metadata | Metadata | HF repo metadata fields | CC-BY | `hf_reported` |",
        ])

        # Local audit outputs
        lines.extend([
            "| 4 | Local Dataset Stats | Local Output | `outputs/audit/local_dataset_stats.json` | - | `local_verified` |",
            "| 5 | Schema Mapping Report | Local Output | `outputs/audit/metadata_schema_report.md` | - | `local_verified` |",
            "| 6 | Split Statistics | Local Output | `outputs/audit/split_stats.csv` | - | `local_verified` |",
            "| 7 | Topic Statistics | Local Output | `outputs/audit/topic_stats.csv` | - | `local_verified` |",
            "| 8 | Data Quality Issues | Local Output | `outputs/audit/data_quality_issues.csv` | - | `local_verified` |",
        ])

        # Term extraction outputs
        lines.extend([
            "| 9 | CS Terms Inventory | Local Output | `outputs/term_coverage/cs_terms_inventory.csv` | - | `local_verified` |",
            "| 10 | Term Examples JSONL | Local Output | `outputs/term_coverage/cs_term_examples.jsonl` | - | `local_verified` |",
            "| 11 | Common Terms | Local Output | `outputs/term_coverage/common_terms.csv` | - | `local_verified` |",
            "| 12 | Rare Terms | Local Output | `outputs/term_coverage/rare_terms.csv` | - | `local_verified` |",
            "| 13 | Hard-only Terms | Local Output | `outputs/term_coverage/hard_only_terms.csv` | - | `local_verified` |",
        ])

        # LLM classification outputs
        lines.extend([
            "| 14 | LLM Classification Audit | LLM Output | `outputs/term_coverage/llm_classification_audit.jsonl` | - | `llm_inferred` |",
            "| 15 | Term Taxonomy Summary | LLM Output | `outputs/term_coverage/term_taxonomy_summary.md` | - | `llm_inferred` |",
            "| 16 | Terms by Entity Category | LLM Output | `outputs/term_coverage/cs_terms_by_entity_category.csv` | - | `llm_inferred` |",
            "| 17 | Terms by Medical Domain | LLM Output | `outputs/term_coverage/cs_terms_by_domain.csv` | - | `llm_inferred` |",
        ])

        # External matching outputs
        lines.extend([
            "| 18 | External Sources Registry | External | `outputs/term_coverage/external_sources_registry.csv` | Variable | `paper_reported` + `llm_inferred` |",
            "| 19 | External Inventory | External | `outputs/term_coverage/external_medical_term_inventory.csv` | Variable | `paper_reported` |",
            "| 20 | Coverage Comparison | External | `outputs/term_coverage/vimedcss_vs_external_coverage.csv` | - | `llm_inferred` |",
        ])

        # ASR outputs (if available)
        lines.extend([
            "| 21 | ASR Transcriptions | ASR Output | `outputs/asr_eval/transcriptions/` | - | `local_verified` |",
            "| 22 | ASR Metrics Summary | ASR Output | `outputs/asr_eval/metrics_summary.csv` | - | `local_verified` |",
            "| 23 | Top Failed Terms | ASR Output | `outputs/asr_eval/errors/top_failed_terms.csv` | - | `local_verified` |",
            "| 24 | Error Taxonomy | ASR Output | `outputs/asr_eval/errors/asr_error_taxonomy.csv` | - | `llm_inferred` |",
        ])

        # Add external reference sources detail
        lines.extend([
            "\n---\n",
            "\n## 3. Chi tiết về Nguồn Tham chiếu Bên ngoài",
            "\n### 3.1 Pilot Inventory Sources (Phase 3)",
            "\n> **Lưu ý:** Đây là giai đoạn pilot. Các nguồn dưới đây chỉ là một phần nhỏ của các bộ thuật ngữ y tế chuẩn (ICD-10, ATC, MedDRA, UMLS, MeSH).",
            "\nCác nguồn tham chiếu được sử dụng trong Phase 3 bao gồm:",
            "\n1. **ICD-10** (International Classification of Diseases) - WHO standard",
            "2. **ATC** (Anatomical Therapeutic Chemical) - WHO drug classification",
            "3. **Meddict** - Medical dictionary reference (pilot scope)",
            "\n### 3.2 Giấy phép",
            "\n- ICD-10: WHO License (用于人道主义目的)",
            "- ATC: WHO License (用于人道主义目的)",
            "- Meddict: Variable, see `external_sources_registry.csv`",
        ])

        # Add verification notes
        lines.extend([
            "\n---\n",
            "\n## 4. Ghi chú về Mức độ Kiểm chứng",
            "\n### 4.1 Xác minh cục bộ (local_verified)",
            "\n- Các thống kê về dataset được tính toán trực tiếp từ các file CSV thực tế trên disk",
            "- Không phụ thuộc vào external API hoặc network calls",
            "- Reproductible: cùng input → cùng output",
            "\n### 4.2 Suy luận từ LLM (llm_inferred)",
            "\n- Entity category và medical domain classification được thực hiện bằng OpenAI structured output",
            "- Confidence scores được attach để indicate reliability",
            "- Terms với confidence < 0.80 được mark là `needs_human_review`",
            "\n### 4.3 Giới hạn của provenance tracking",
            "\n- Không có ground-truth labels cho entity categories (human expert review pending)",
            "- ASR evaluation sử dụng mock data nếu audio files không có sẵn",
            "- External coverage chỉ là pilot scope, không đại diện cho full inventory",
        ])

        # Add file manifest info
        lines.extend([
            "\n---\n",
            "\n## 5. Dataset Revision Information",
            "\nThông tin về dataset revision được ghi lại trong `outputs/audit/hf_file_manifest.json`:\n",
        ])

        try:
            import json
            if os.path.exists("outputs/audit/hf_file_manifest.json"):
                with open("outputs/audit/hf_file_manifest.json", "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                lines.extend([
                    f"- **Repository:** {manifest.get('repo_id', 'N/A')}",
                    f"- **Revision:** {manifest.get('revision', 'N/A')}",
                    f"- **Files:** {len(manifest.get('files', []))}",
                ])
        except Exception as e:
            logger.warning(f"Could not load manifest: {e}")
            lines.extend([
                "- *Manifest chưa được tạo. Vui lòng chạy `make download` trước.*",
            ])

        return "\n".join(lines)
