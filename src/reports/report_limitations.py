"""Limitation writer module for ViMedCSS evaluation pipeline.

This module provides the LimitationWriter class that generates a limitations document
detailing the scope, caveats, and constraints of the evaluation pipeline.
"""

import os
import datetime
from typing import Dict, Any, Optional
from src.shared.logging import setup_logger

logger = setup_logger("reports.limitations")


class LimitationWriter:
    """Writer for report limitations and caveats.

    This class generates a markdown document detailing the limitations,
    scope constraints, and caveats of the ViMedCSS evaluation pipeline.
    """

    def __init__(
        self,
        dataset_config: Dict[str, Any],
        taxonomy_config: Dict[str, Any],
        external_config: Dict[str, Any],
    ):
        """Initialize the LimitationWriter.

        Args:
            dataset_config: Dataset configuration dict
            taxonomy_config: Taxonomy configuration dict
            external_config: External reference configuration dict
        """
        self.dataset_config = dataset_config
        self.taxonomy_config = taxonomy_config
        self.external_config = external_config
        self.output_dir = "outputs/reports"
        os.makedirs(self.output_dir, exist_ok=True)

    def generate(self, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate the limitations report file.

        Args:
            context: Rendering context (optional)

        Returns:
            Path to the generated report file
        """
        content = self.generate_report_content(context or {})

        output_path = os.path.join(self.output_dir, "report_limitations.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Limitations report written to {output_path}")
        return output_path

    def generate_report_content(self, context: Dict[str, Any]) -> str:
        """Generate the limitations report content.

        Args:
            context: Rendering context with pipeline data

        Returns:
            Markdown content for the limitations document
        """
        lines = [
            "# Giới hạn của Phân tích",
            f"\n*Ngày tạo: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n",
            "\n---\n",
            "\n## 1. Tổng quan",
            "\nBáo cáo này document các giới hạn, caveats, và constraints của ViMedCSS "
            "evaluation pipeline. Việc hiểu rõ các giới hạn này là cần thiết để interpret "
            "kết quả đúng cách.",
            "\n---\n",
            "\n## 2. Giới hạn về Phạm vi Pilot External Inventory",
            "\n> **Scope:** Phase 3 sử dụng pilot external inventory chỉ bao gồm 5 thuật ngữ tham chiếu.",
            "\n### 2.1 Nguồn tham chiếu",
            "\n- **ICD-10**: International Classification of Diseases (pilot subset)",
            "- **ATC**: Anatomical Therapeutic Chemical classification (pilot subset)",
            "- **Meddict**: Medical dictionary reference (pilot scope)",
            "\n### 2.2 Hạn chế",
            "\n- Coverage ratio hiện tại (0.11%) **không** đại diện cho tỷ lệ phủ sóng thực tế",
            "- Pilot inventory được tạo để smoke-test matching logic, không phải comprehensive review",
            "- Cần bổ sung thêm source inventories (UMLS, MeSH, SNOMED-CT) để coverage meaningful",
            "\n---\n",
            "\n## 3. Tỷ lệ Term cần Human Review",
            "\n> **Statistics:** 76% terms (676/889) được mark là `needs_human_review`.",
            "\n### 3.1 Nguyên nhân",
            "\n1. **LLM Classification ở chế độ Mock:** Entity categories được assign bằng rule-based heuristics "
            "thay vì actual OpenAI API calls",
            "2. **Low Confidence Scores:** Terms được classify với confidence = 0.50 (mock default)",
            "3. **Ambiguous Contexts:** Nhiều terms có dual meanings (ví dụ: 'gram' = unit of mass vs microbiology term)",
            "\n### 3.2 Đề xuất",
            "\n- Chạy Phase 3 với `--mock=False` để sử dụng actual OpenAI API",
            "- Human expert review các term có confidence < 0.80",
            "- Validate entity categories với medical domain experts",
            "\n---\n",
            "\n## 4. Giới hạn về UMLS/MeSH API",
            "\n> **Constraint:** Sandbox environment không có access đến UMLS/MeSH APIs.",
            "\n### 4.1 Hạn chế",
            "\n- Không thể verify terms against standard medical vocabularies in real-time",
            "- External coverage matching chỉ sử dụng local pilot inventory",
            "- Không thể resolve UMLS CUIs hoặc MeSH descriptors",
            "\n### 4.2 Workaround",
            "\n- Sử dụng offline reference files nếu có sẵn",
            "- Manual verification cho critical terms",
            "- Future: integrate UMLS API when in proper environment",
            "\n---\n",
            "\n## 5. Trạng thái ASR Evaluation",
            "\n> **Status:** ASR evaluation có thể ở một trong các trạng thái: completed, pending, hoặc mock.",
            "\n### 5.1 Trạng thái có thể có",
            "\n| Trạng thái | Mô tả | Khi nào xảy ra |",
            "|---|---|---|",
            "| **Completed** | Full ASR evaluation đã chạy | Audio files available, Phase 4 completed |",
            "| **Pending** | Phase 4 chưa chạy | `outputs/asr_eval/` artifacts missing |",
            "| **Mock** | Mock ASR results | `--mock` flag used, no actual audio |",
            "\n### 5.2 Điều kiện để có complete ASR evaluation",
            "\n1. Audio files phải có sẵn trong `data/raw/vimedcss/`",
            "2. Chạy `make asr` để transcribe audio",
            "3. Chạy `make eval-asr` để compute metrics",
            "\n---\n",
            "\n## 6. Giới hạn về LLM Classification",
            "\n### 6.1 Confidence Scores",
            "\nLLM classification outputs bao gồm confidence scores:",
            "\n- **High confidence (≥0.80)**: Term classification đáng tin cậy",
            "- **Medium confidence (0.60-0.79)**: Cần thêm evidence hoặc review",
            "- **Low confidence (<0.60)**: Mock classification, cần human expert review",
            "\n### 6.2 Evidence và Uncertainty",
            "\nMỗi LLM classification bao gồm:",
            "\n- **Evidence**: Quote từ source contexts hỗ trợ classification",
            "- **Uncertainty**: Giải thích về lý do uncertain hoặc ambiguous",
            "- **needs_human_review**: Boolean flag chỉ định cần expert review",
            "\n### 6.3 Giới hạn của Mock Classification",
            "\n> **Warning:** Khi sử dụng `--mock` flag, tất cả classifications được assign "
            "với confidence = 0.50 và mock evidence strings.",
            "\n---\n",
            "\n## 7. Dataset Snapshot và Revision",
            "\n### 7.1 Dataset Revision",
            "\nDataset snapshot information được ghi lại trong `outputs/audit/hf_file_manifest.json`:",
            "\n"
        ]

        # Add revision info if available
        try:
            import json
            if os.path.exists("outputs/audit/hf_file_manifest.json"):
                with open("outputs/audit/hf_file_manifest.json", "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                lines.extend([
                    f"- **Repository:** `{manifest.get('repo_id', 'N/A')}`",
                    f"- **Revision:** `{manifest.get('revision', 'N/A')}`",
                    f"- **Download timestamp:** {manifest.get('downloaded_at', 'N/A')}",
                ])
            else:
                lines.extend([
                    "- *Manifest chưa được tạo. Chạy `make download` để tạo.*",
                ])
        except Exception as e:
            logger.warning(f"Could not load manifest: {e}")
            lines.extend([
                "- *Không thể load manifest: error occurred*",
            ])

        lines.extend([
            "\n### 7.2 Reproducibility",
            "\nĐể reproduce results với cùng dataset revision:",
            "\n```bash",
            "export HF_DATASET_REVISION=<revision_hash>",
            "make download",
            "make audit",
            "make terms",
            "make classify",
            "make report",
            "```",
            "\n---\n",
            "\n## 8. Bias về Medical Topics và Code-Switching",
            "\n### 8.1 Topic Distribution Bias",
            "\nDataset topic distribution không uniform:",
            "\n- **Medical Sciences** (44.1%): Over-represented",
            "- **Pathology & Pathogens** (29.6%): Over-represented",
            "- **Nutrition** (3.9%): Under-represented",
            "\nĐiều này có thể affect generalization của ASR models trained on this data.",
            "\n### 8.2 Code-Switching Patterns",
            "\nCS patterns observed in dataset:",
            "\n- **Intra-sentential CS**: English medical terms embedded within Vietnamese sentences",
            "- **Frequency variation**: Term frequency không uniform across splits",
            "- **Spelling variation**: Same term có thể xuất hiện với nhiều forms (e.g., 'inulin' vs 'insulin')",
            "\n### 8.3 Implications",
            "\n- ASR models có thể perform differently trên CS patterns chưa thấy trong training",
            "- Term coverage analysis có thể không reflect full medical vocabulary usage",
            "- Hard split chứa rare terms không representative của general medical speech",
            "\n---\n",
            "\n## 9. Kết luận",
            "\nCác giới hạn trên cần được consider khi interpret results từ ViMedCSS evaluation pipeline. "
            "Đặc biệt:",
            "\n1. **Pilot scope** của external coverage không meaningful cho comprehensive assessment",
            "2. **Mock LLM classification** không suitable cho production decisions",
            "3. **ASR status** phải được verified trước khi trust ASR-related conclusions",
            "4. **Human review** là cần thiết cho tất cả term classifications trước khi sử dụng trong production",
            "\n---\n",
            "\n*Document này được auto-generated bởi ViMedCSS evaluation pipeline.*\n",
        ])

        return "\n".join(lines)
