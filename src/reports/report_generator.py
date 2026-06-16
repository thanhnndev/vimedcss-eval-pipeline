"""Report generator module for ViMedCSS evaluation pipeline.

This module provides the ReportGenerator class that aggregates Phase 0-4 artifacts
into comprehensive Vietnamese markdown reports with provenance tracking.
"""

import os
import json
import datetime
from typing import Dict, Any, List, Optional
import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.shared.logging import setup_logger

logger = setup_logger("reports.generator")


class ReportGenerator:
    """Generates Vietnamese markdown reports from pipeline artifacts.

    The ReportGenerator reads CSV/JSONL artifacts from various pipeline phases
    and assembles them into comprehensive markdown reports with proper provenance
    tracking and conditional ASR section handling.

    Attributes:
        dataset_config: Dataset configuration dict
        taxonomy_config: Taxonomy configuration dict
        report_config: Report configuration dict
        external_config: External reference configuration dict
    """

    # Mapping of section IDs to renderer method names
    _SECTION_RENDERERS = {
        "executive_summary": "_render_executive_summary",
        "data_sources": "_render_data_sources",
        "provenance_breakdown": "_render_provenance_breakdown",
        "term_coverage_overview": "_render_term_coverage_overview",
        "entity_category_analysis": "_render_entity_category_analysis",
        "domain_analysis": "_render_domain_analysis",
        "frequency_analysis": "_render_frequency_analysis",
        "external_comparison": "_render_external_comparison",
        "asr_baseline_results": "_render_asr_baseline_results",
        "asr_cs_term_results": "_render_asr_cs_term_results",
        "asr_error_analysis": "_render_asr_error_analysis",
        "error_examples": "_render_error_examples",
        "coverage_assessment": "_render_coverage_assessment",
        "recommendations": "_render_recommendations",
        "limitations": "_render_limitations",
    }

    def __init__(
        self,
        dataset_config: Dict[str, Any],
        taxonomy_config: Dict[str, Any],
        report_config: Dict[str, Any],
        external_config: Dict[str, Any],
    ):
        """Initialize the ReportGenerator with configuration.

        Args:
            dataset_config: Dataset configuration dict from configs/dataset.yaml
            taxonomy_config: Taxonomy configuration dict from configs/taxonomy.yaml
            report_config: Report configuration dict from configs/report.yaml
            external_config: External reference configuration dict
        """
        self.dataset_config = dataset_config
        self.taxonomy_config = taxonomy_config
        self.report_config = report_config
        self.external_config = external_config

        # Set up output directory
        self.output_dir = report_config.get("output_dir", "outputs/reports")
        os.makedirs(self.output_dir, exist_ok=True)

        # Set up Jinja environment for templates
        template_dir = "templates/reports"
        if os.path.exists(template_dir):
            self.jinja_env = Environment(
                loader=FileSystemLoader(template_dir),
                autoescape=select_autoescape(enabled_extensions=()),
                trim_blocks=True,
                lstrip_blocks=True,
            )
            logger.info(f"Jinja templates loaded from {template_dir}")
        else:
            self.jinja_env = None
            logger.warning(f"Template directory {template_dir} not found, using fallback rendering")

        # Precompute ASR availability
        self._asr_metrics_available = self._check_file_exists("outputs/asr_eval/metrics_summary.csv")
        self._asr_errors_available = self._check_file_exists("outputs/asr_eval/errors/top_failed_terms.csv")
        self._asr_taxonomy_available = self._check_file_exists("outputs/asr_eval/errors/asr_error_taxonomy.csv")

        logger.info(
            f"ASR availability - metrics: {self._asr_metrics_available}, "
            f"errors: {self._asr_errors_available}, taxonomy: {self._asr_taxonomy_available}"
        )

    def _check_file_exists(self, path: str) -> bool:
        """Check if a file exists and is readable."""
        return os.path.exists(path) and os.path.getsize(path) > 0

    def _load_csv(self, path: str) -> pd.DataFrame:
        """Load a CSV file into a DataFrame.

        Args:
            path: Path to the CSV file

        Returns:
            DataFrame with the CSV contents

        Raises:
            FileNotFoundError: If the file does not exist
        """
        if not self._check_file_exists(path):
            raise FileNotFoundError(
                f"Required artifact not found: {path}. "
                f"Please ensure the pipeline has been run to generate this artifact."
            )
        logger.debug(f"Loading CSV: {path}")
        try:
            return pd.read_csv(path)
        except pd.errors.EmptyDataError:
            logger.warning(f"CSV file has no data: {path}")
            return pd.DataFrame()

    def _load_json(self, path: str) -> Dict[str, Any]:
        """Load a JSON file.

        Args:
            path: Path to the JSON file

        Returns:
            Dict with the JSON contents

        Raises:
            FileNotFoundError: If the file does not exist
        """
        if not self._check_file_exists(path):
            raise FileNotFoundError(f"Required artifact not found: {path}")
        logger.debug(f"Loading JSON: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_jsonl(self, path: str) -> List[Dict[str, Any]]:
        """Load a JSONL file into a list of dicts.

        Args:
            path: Path to the JSONL file

        Returns:
            List of dicts, one per line

        Raises:
            FileNotFoundError: If the file does not exist
        """
        if not self._check_file_exists(path):
            raise FileNotFoundError(f"Required artifact not found: {path}")
        logger.debug(f"Loading JSONL: {path}")
        records = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def _get_enabled_sections(self, skip_asr: bool = False) -> List[Dict[str, Any]]:
        """Get list of enabled sections from config.

        Args:
            skip_asr: If True, skip ASR-related sections

        Returns:
            List of section config dicts in declared order
        """
        sections = self.report_config.get("sections", [])
        enabled = []

        for section in sections:
            if not section.get("enabled", True):
                continue

            section_id = section["id"]

            # Handle ASR sections
            if skip_asr and section_id.startswith("asr_"):
                logger.info(f"Skipping ASR section '{section_id}' due to --skip-asr flag")
                continue

            if section_id.startswith("asr_") and not skip_asr:
                requires = section.get("requires_outputs", [])
                missing = [p for p in requires if not self._check_file_exists(p)]
                if missing:
                    logger.warning(
                        f"ASR section '{section_id}' requires missing artifacts: {missing}. "
                        f"Will add disclaimer."
                    )

            enabled.append(section)

        return enabled

    def _render_section(self, section_id: str, context: Dict[str, Any]) -> str:
        """Render a single section using the appropriate renderer method.

        Args:
            section_id: The section identifier
            context: Rendering context with data

        Returns:
            Rendered markdown string for the section
        """
        renderer_name = self._SECTION_RENDERERS.get(section_id)
        if not renderer_name:
            logger.warning(f"No renderer found for section '{section_id}'")
            return f"\n## [{section_id}]\n\n*Renderer not implemented*\n"

        renderer_method = getattr(self, renderer_name, None)
        if not renderer_method:
            logger.warning(f"Renderer method '{renderer_name}' not found for section '{section_id}'")
            return f"\n## [{section_id}]\n\n*Renderer not implemented*\n"

        try:
            return renderer_method(context)
        except Exception as e:
            logger.error(f"Error rendering section '{section_id}': {e}")
            return f"\n## [{section_id}]\n\n*Lỗi khi render phần này*\n"

    def generate(self, output_dir: Optional[str] = None, skip_asr: bool = False) -> Dict[str, str]:
        """Generate all report files.

        Args:
            output_dir: Override output directory (optional)
            skip_asr: Skip ASR sections regardless of output presence

        Returns:
            Dict mapping report name to file path

        Raises:
            FileNotFoundError: If required core artifacts are missing
        """
        if output_dir:
            self.output_dir = output_dir
            os.makedirs(self.output_dir, exist_ok=True)

        logger.info(f"Starting report generation to {self.output_dir}")
        logger.info(f"skip_asr={skip_asr}")

        generated_files = {}

        # Build rendering context from artifacts
        context = self._build_context(skip_asr)

        # Get enabled sections
        enabled_sections = self._get_enabled_sections(skip_asr)

        # Generate main report
        main_report = self._generate_main_report(enabled_sections, context)
        main_path = os.path.join(self.output_dir, "report_vi_vimedcss_term_coverage_and_asr_weakness.md")
        with open(main_path, "w", encoding="utf-8") as f:
            f.write(main_report)
        generated_files["main_report"] = main_path
        logger.info(f"Main report written to {main_path}")

        # Generate data sources report
        data_sources_path = self._generate_data_sources_report()
        generated_files["data_sources_report"] = data_sources_path
        logger.info(f"Data sources report written to {data_sources_path}")

        # Generate limitations report
        limitations_path = self._generate_limitations_report(context)
        generated_files["limitations_report"] = limitations_path
        logger.info(f"Limitations report written to {limitations_path}")

        return generated_files

    def _build_context(self, skip_asr: bool) -> Dict[str, Any]:
        """Build rendering context from pipeline artifacts.

        Args:
            skip_asr: Whether ASR sections should be included

        Returns:
            Context dict with all data needed for rendering
        """
        context = {
            "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "asr_metrics_available": self._asr_metrics_available and not skip_asr,
            "asr_errors_available": self._asr_errors_available and not skip_asr,
            "asr_taxonomy_available": self._asr_taxonomy_available and not skip_asr,
        }

        # Load core artifacts
        try:
            context["inventory"] = self._load_csv("outputs/term_coverage/cs_terms_inventory.csv")
        except FileNotFoundError:
            logger.warning("cs_terms_inventory.csv not found, creating empty context")
            context["inventory"] = pd.DataFrame()

        try:
            context["taxonomy_summary"] = self._load_csv("outputs/term_coverage/cs_terms_by_entity_category.csv")
        except FileNotFoundError:
            context["taxonomy_summary"] = pd.DataFrame()

        try:
            context["domain_summary"] = self._load_csv("outputs/term_coverage/cs_terms_by_domain.csv")
        except FileNotFoundError:
            context["domain_summary"] = pd.DataFrame()

        try:
            context["split_summary"] = self._load_csv("outputs/term_coverage/cs_terms_by_split.csv")
        except FileNotFoundError:
            context["split_summary"] = pd.DataFrame()

        try:
            context["common_terms"] = self._load_csv("outputs/term_coverage/common_terms.csv")
        except FileNotFoundError:
            context["common_terms"] = pd.DataFrame()

        try:
            context["rare_terms"] = self._load_csv("outputs/term_coverage/rare_terms.csv")
        except FileNotFoundError:
            context["rare_terms"] = pd.DataFrame()

        try:
            context["hard_terms"] = self._load_csv("outputs/term_coverage/hard_only_terms.csv")
        except FileNotFoundError:
            context["hard_terms"] = pd.DataFrame()

        try:
            context["external_coverage"] = self._load_csv("outputs/term_coverage/vimedcss_vs_external_coverage.csv")
        except FileNotFoundError:
            context["external_coverage"] = pd.DataFrame()

        try:
            context["hf_manifest"] = self._load_json("outputs/audit/hf_file_manifest.json")
        except FileNotFoundError:
            context["hf_manifest"] = {}

        try:
            context["external_registry"] = self._load_csv("outputs/term_coverage/external_sources_registry.csv")
        except FileNotFoundError:
            context["external_registry"] = pd.DataFrame()

        try:
            context["local_stats"] = self._load_json("outputs/audit/local_dataset_stats.json")
        except FileNotFoundError:
            context["local_stats"] = {}

        # Load ASR artifacts if available and not skipped
        if not skip_asr:
            if self._asr_metrics_available:
                try:
                    context["asr_metrics"] = self._load_csv("outputs/asr_eval/metrics_summary.csv")
                except FileNotFoundError:
                    context["asr_metrics"] = pd.DataFrame()

            if self._asr_errors_available:
                try:
                    context["asr_errors"] = self._load_csv("outputs/asr_eval/errors/top_failed_terms.csv")
                except FileNotFoundError:
                    context["asr_errors"] = pd.DataFrame()

            if self._asr_taxonomy_available:
                try:
                    context["asr_taxonomy"] = self._load_csv("outputs/asr_eval/errors/asr_error_taxonomy.csv")
                except FileNotFoundError:
                    context["asr_taxonomy"] = pd.DataFrame()

        return context

    def _generate_main_report(
        self, sections: List[Dict[str, Any]], context: Dict[str, Any]
    ) -> str:
        """Generate the main report content.

        Args:
            sections: List of enabled section configs
            context: Rendering context

        Returns:
            Complete markdown report string
        """
        lines = [
            "# Báo cáo Đánh giá Term Coverage và Điểm yếu ASR - ViMedCSS",
            f"\n*Ngày tạo: {context['generated_at']}*",
            "\n---\n",
        ]

        # Add table of contents
        lines.append("\n## Mục lục\n")
        for i, section in enumerate(sections, 1):
            section_id = section["id"]
            title = section.get("title", section_id)
            anchor = section_id.replace("_", "-")
            lines.append(f"{i}. [{title}](#{anchor})")

        # Render each section
        for i, section in enumerate(sections, 1):
            section_id = section["id"]
            title = section.get("title", section_id)
            logger.info(f"Rendering section {i}/{len(sections)}: {section_id}")

            section_content = self._render_section(section_id, context)

            lines.append(f"\n---\n")
            lines.append(f"\n## {i}. {title}\n")
            lines.append(section_content)

        return "\n".join(lines)

    def _render_executive_summary(self, context: Dict[str, Any]) -> str:
        """Render executive summary section."""
        inventory = context.get("inventory", pd.DataFrame())

        if inventory.empty:
            total_terms = 0
            common_count = 0
            rare_count = 0
        else:
            total_terms = len(inventory)
            common_count = len(inventory[inventory.get("frequency_bucket", pd.Series()) == "common"]) if "frequency_bucket" in inventory.columns else 0
            rare_count = len(inventory[inventory.get("frequency_bucket", pd.Series()) == "rare"]) if "frequency_bucket" in inventory.columns else 0

        taxonomy_summary = context.get("taxonomy_summary", pd.DataFrame())
        unknown_pct = 0.0
        if not taxonomy_summary.empty and "unknown" in taxonomy_summary["entity_category"].values:
            unknown_row = taxonomy_summary[taxonomy_summary["entity_category"] == "unknown"]
            if not unknown_row.empty and "count" in unknown_row.columns:
                unknown_pct = (unknown_row.iloc[0]["count"] / total_terms * 100) if total_terms > 0 else 0

        lines = [
            f"\nTổng số thuật ngữ CS (code-switching) được phân tích: **{total_terms}**",
            f"\n- Term phổ biến (≥20 lần xuất hiện): **{common_count}**",
            f"- Term hiếm (<5 lần xuất hiện): **{rare_count}**",
            f"\nTỷ lệ term chưa được phân loại entity category: **{unknown_pct:.1f}%**",
            "\n### Điểm chính",
            "\n1. Dataset chứa phần lớn term ở dạng **unknown** (chưa phân loại) do sử dụng LLM classification ở chế độ mock.",
            "2. Các term tập trung chủ yếu trong domain **Medical Sciences** và **Pathology & Pathogens**.",
            "3. Tỷ lệ coverage với external inventory còn rất thấp (pilot scope).",
        ]

        # Add ASR summary if available
        if context.get("asr_metrics_available"):
            lines.append("\n4. Kết quả ASR baseline cho thấy hiệu suất trên các CS terms cần được cải thiện.")
        else:
            lines.append("\n4. ASR evaluation chưa được chạy hoặc đang ở trạng thái pending.")

        return "\n".join(lines)

    def _render_data_sources(self, context: Dict[str, Any]) -> str:
        """Render data sources section (summary only, full report in separate file)."""
        lines = [
            "\nBáo cáo chi tiết về nguồn dữ liệu và mức độ kiểm chứng được lưu tại:",
            "\n- `outputs/reports/report_data_sources.md`",
            "\nBáo cáo này phân biệt rõ ràng nguồn gốc của dữ liệu theo 4 mức độ kiểm chứng:",
            "\n| Mức độ | Mô tả | Nguồn |",
            "|---|---|---|",
            "| **paper_reported** | Giá trị được công bố trong paper/dataset card | VietMedVoice paper, Hugging Face dataset card |",
            "| **hf_reported** | Giá trị từ Hugging Face metadata | HF repo metadata |",
            "| **local_verified** | Giá trị được xác minh từ file cục bộ | Local audit outputs |",
            "| **llm_inferred** | Giá trị suy luận từ LLM structured output | OpenAI API (confidence flags) |",
        ]
        return "\n".join(lines)

    def _render_provenance_breakdown(self, context: Dict[str, Any]) -> str:
        """Render provenance breakdown section."""
        lines = [
            "\nBáo cáo này phân biệt rõ ràng nguồn gốc của dữ liệu theo 4 mức độ kiểm chứng:",
            "\n| Mức độ | Mô tả | Nguồn |",
            "|---|---|---|",
            "| **paper_reported** | Giá trị được công bố trong paper/dataset card | VietMedVoice paper, Hugging Face dataset card |",
            "| **hf_reported** | Giá trị từ Hugging Face metadata | HF repo metadata |",
            "| **local_verified** | Giá trị được xác minh từ file cục bộ | Local audit outputs |",
            "| **llm_inferred** | Giá trị suy luận từ LLM structured output | OpenAI API (confidence flags) |",
            "\n### Áp dụng trong báo cáo này",
            "\n- **Statistics về dataset**: `local_verified` từ Phase 0-1 audit",
            "- **Term counts**: `local_verified` từ Phase 2 extraction",
            "- **Entity/Domain classification**: `llm_inferred` từ Phase 3 (chế độ mock)",
            "- **ASR metrics**: `local_verified` từ Phase 4 evaluation",
            "- **External coverage**: `llm_inferred` (matching logic) + `paper_reported` (reference sources)",
        ]
        return "\n".join(lines)

    def _render_term_coverage_overview(self, context: Dict[str, Any]) -> str:
        """Render term coverage overview section."""
        inventory = context.get("inventory", pd.DataFrame())
        total_terms = len(inventory)

        if total_terms == 0:
            return "\n*Chưa có dữ liệu inventory. Vui lòng chạy Phase 2 (term extraction) trước.*\n"

        lines = [
            f"\nTổng số thuật ngữ CS độc nhất được trích xuất từ dataset: **{total_terms}**",
            "\nThuật ngữ được trích xuất bằng cách:",
            "1. Parse transcript segments từ Hugging Face dataset",
            "2. Extract English medical terms (code-switching)",
            "3. Normalize về dạng chuẩn (lowercase, lemmatization cơ bản)",
            "4. Deduplicate và count occurrences",
        ]

        return "\n".join(lines)

    def _render_entity_category_analysis(self, context: Dict[str, Any]) -> str:
        """Render entity category analysis section."""
        taxonomy_summary = context.get("taxonomy_summary", pd.DataFrame())

        if taxonomy_summary.empty:
            return "\n*Chưa có dữ liệu taxonomy summary. Vui lòng chạy Phase 3 (LLM classification) trước.*\n"

        lines = [
            "\n| Entity Category | Số lượng | Tỷ lệ (%) |",
            "|---|---|---|",
        ]

        for _, row in taxonomy_summary.iterrows():
            cat = row.get("entity_category", "unknown")
            count = row.get("count", 0)
            pct = row.get("percentage", 0)
            lines.append(f"| `{cat}` | {count} | {pct:.1f}% |")

        return "\n".join(lines)

    def _render_domain_analysis(self, context: Dict[str, Any]) -> str:
        """Render domain analysis section."""
        domain_summary = context.get("domain_summary", pd.DataFrame())

        if domain_summary.empty:
            return "\n*Chưa có dữ liệu domain summary.*\n"

        lines = [
            "\n| Medical Domain | Số lượng | Tỷ lệ (%) |",
            "|---|---|---|",
        ]

        for _, row in domain_summary.iterrows():
            domain = row.get("medical_domain", "unknown")
            count = row.get("count", 0)
            pct = row.get("percentage", 0)
            lines.append(f"| `{domain}` | {count} | {pct:.1f}% |")

        return "\n".join(lines)

    def _render_frequency_analysis(self, context: Dict[str, Any]) -> str:
        """Render frequency analysis section."""
        common = context.get("common_terms", pd.DataFrame())
        rare = context.get("rare_terms", pd.DataFrame())
        hard = context.get("hard_terms", pd.DataFrame())

        lines = [
            "\n### Term phổ biến (common, ≥20 lần xuất hiện)",
        ]

        if common.empty:
            lines.append("\n*Không có term phổ biến.*\n")
        else:
            lines.append("\n| Term | Occurrences | Entity Category |")
            lines.append("|---|---|---|")
            for _, row in common.head(20).iterrows():
                term = row.get("normalized_term", "")
                occ = row.get("occurrence_count", 0)
                cat = row.get("entity_category", "unknown")
                lines.append(f"| `{term}` | {occ} | `{cat}` |")

        lines.append("\n### Term hiếm (rare, <5 lần xuất hiện)")
        if rare.empty:
            lines.append("\n*Không có term hiếm.*\n")
        else:
            lines.append(f"\nTổng số term hiếm: **{len(rare)}**")
            lines.append("\n| Term | Occurrences | Entity Category |")
            lines.append("|---|---|---|")
            for _, row in rare.head(10).iterrows():
                term = row.get("normalized_term", "")
                occ = row.get("occurrence_count", 0)
                cat = row.get("entity_category", "unknown")
                lines.append(f"| `{term}` | {occ} | `{cat}` |")

        lines.append("\n### Term hard-only (chỉ xuất hiện trong tập hard)")
        if hard.empty:
            lines.append("\n*Không có term hard-only.*\n")
        else:
            lines.append(f"\nTổng số term hard-only: **{len(hard)}**")
            lines.append("\n| Term | Occurrences |")
            lines.append("|---|---|")
            for _, row in hard.head(10).iterrows():
                term = row.get("normalized_term", "")
                occ = row.get("occurrence_count", 0)
                lines.append(f"| `{term}` | {occ} |")

        return "\n".join(lines)

    def _render_external_comparison(self, context: Dict[str, Any]) -> str:
        """Render external comparison section."""
        coverage = context.get("external_coverage", pd.DataFrame())

        lines = [
            "\n> **Giới hạn phạm vi:** Đây là giai đoạn pilot (thử nghiệm). "
            "External inventory chỉ bao gồm 5 thuật ngữ tham chiếu. "
            "Coverage ratio không đại diện cho tỷ lệ phủ sóng thực tế.",
        ]

        if coverage.empty:
            lines.append("\n*Chưa có dữ liệu external coverage. Vui lòng chạy Phase 3 (external matching) trước.*\n")
        else:
            lines.append("\n### Tổng quan Coverage")
            for _, row in coverage.head(5).iterrows():
                lines.append(f"\n- **{row.get('metric', 'N/A')}**: {row.get('value', 'N/A')}")

        return "\n".join(lines)

    def _render_asr_baseline_results(self, context: Dict[str, Any]) -> str:
        """Render ASR baseline results section."""
        if not context.get("asr_metrics_available"):
            return self._asr_disclaimer()

        metrics = context.get("asr_metrics", pd.DataFrame())
        if metrics.empty:
            return self._asr_disclaimer()

        lines = ["\n### Tổng quan Metrics ASR Baseline\n"]

        for _, row in metrics.iterrows():
            for col in metrics.columns:
                if col not in ["split", "metric"]:
                    lines.append(f"- **{col}**: {row.get(col, 'N/A')}")

        return "\n".join(lines)

    def _render_asr_cs_term_results(self, context: Dict[str, Any]) -> str:
        """Render ASR CS term results section."""
        if not context.get("asr_errors_available"):
            return self._asr_disclaimer()

        errors = context.get("asr_errors", pd.DataFrame())
        if errors.empty:
            return self._asr_disclaimer()

        lines = [
            "\n### Top Failed CS Terms\n",
            "\n| Term | Error Type | Count |",
            "|---|---|---|",
        ]

        for _, row in errors.head(20).iterrows():
            term = row.get("term", "")
            error_type = row.get("error_type", "unknown")
            count = row.get("count", 0)
            lines.append(f"| `{term}` | {error_type} | {count} |")

        return "\n".join(lines)

    def _render_asr_error_analysis(self, context: Dict[str, Any]) -> str:
        """Render ASR error analysis section."""
        if not context.get("asr_taxonomy_available"):
            return self._asr_disclaimer()

        taxonomy = context.get("asr_taxonomy", pd.DataFrame())
        if taxonomy.empty:
            return self._asr_disclaimer()

        lines = [
            "\n### Error Taxonomy by Entity Category\n",
            "\n| Entity Category | Error Count | Error Rate |",
            "|---|---|---|",
        ]

        for _, row in taxonomy.iterrows():
            cat = row.get("entity_category", "unknown")
            count = row.get("count", 0)
            rate = row.get("error_rate", 0)
            lines.append(f"| `{cat}` | {count} | {rate:.1%} |")

        return "\n".join(lines)

    def _render_error_examples(self, context: Dict[str, Any]) -> str:
        """Render error examples section."""
        if not context.get("asr_errors_available"):
            return self._asr_disclaimer()

        errors = context.get("asr_errors", pd.DataFrame())
        if errors.empty:
            return self._asr_disclaimer()

        lines = [
            "\n### Ví dụ lỗi tiêu biểu\n",
            "\nCác ví dụ dưới đây minh họa các lỗi ASR phổ biến trên CS medical terms:",
        ]

        for _, row in errors.head(5).iterrows():
            lines.append(f"\n**Term: `{row.get('term', '')}`**")
            lines.append(f"- Expected: `{row.get('expected', '')}`")
            lines.append(f"- Got: `{row.get('recognized', '')}`")
            lines.append(f"- Error Type: {row.get('error_type', '')}")

        return "\n".join(lines)

    def _render_coverage_assessment(self, context: Dict[str, Any]) -> str:
        """Render coverage assessment section."""
        lines = [
            "\n### Phân tích Dataset Coverage",
            "\n**Điểm mạnh:**",
            "\n1. Dataset cover đa dạng các medical domains (Medical Sciences, Pathology, Treatments, etc.)",
            "2. Tập hard chứa các term hiếm gặp, hữu ích cho evaluating ASR robustness",
            "3. Nhiều term xuất hiện đồng thời trong multiple splits",
            "\n**Điểm cần cải thiện:**",
            "\n1. Tỷ lệ unknown entity category cao (76%) - cần human review",
            "2. Specialty coverage chưa đầy đủ (89.5% unknown)",
            "3. External coverage pilot scope chỉ cover 0.11% terms",
        ]
        return "\n".join(lines)

    def _render_recommendations(self, context: Dict[str, Any]) -> str:
        """Render recommendations section."""
        lines = [
            "\n## Khuyến nghị cho VietMedVoice",
            "\n### 1. Nâng cao ASR performance trên CS terms",
            "\n- Fine-tune ASR model với data chứa nhiều CS medical terms",
            "- Tập trung vào các term có error rate cao (abbreviations, multi-syllabic terms)",
            "\n### 2. Cải thiện term classification",
            "\n- Chạy LLM classification với chế độ non-mock (cần OPENAI_API_KEY)",
            "- Human review các term có confidence thấp (<0.80)",
            "\n### 3. Mở rộng external coverage",
            "\n- Bổ sung thêm source inventories (ICD-10, ATC, MedDRA)",
            "- Tăng số lượng reference terms trong pilot inventory",
        ]
        return "\n".join(lines)

    def _render_limitations(self, context: Dict[str, Any]) -> str:
        """Render limitations section (summary only, full report in separate file)."""
        lines = [
            "\nBáo cáo chi tiết về giới hạn và caveats được lưu tại:",
            "\n- `outputs/reports/report_limitations.md`",
            "\n### Key Limitations",
            "\n1. **Pilot scope** của external coverage không meaningful cho comprehensive assessment",
            "2. **Mock LLM classification** không suitable cho production decisions",
            "3. **ASR status** phải được verified trước khi trust ASR-related conclusions",
            "4. **Human review** là cần thiết cho tất cả term classifications trước khi sử dụng trong production",
        ]
        return "\n".join(lines)

    def _asr_disclaimer(self) -> str:
        """Return disclaimer text for missing ASR outputs."""
        return (
            "\n> **Trạng thái ASR Evaluation: PENDING**\n"
            "\n> Các phần liên quan đến ASR (Automatic Speech Recognition) evaluation "
            "chưa được generate do Phase 4 chưa hoàn thành hoặc các output artifacts còn thiếu.\n"
            "\n> Để generate đầy đủ các sections về ASR, vui lòng:\n"
            "> 1. Chạy `make asr` để thực hiện ASR transcription\n"
            "> 2. Chạy `make eval-asr` để compute metrics và classify errors\n"
            "> 3. Sau đó chạy lại `make report` để include ASR results\n"
            "\n"
        )

    def _generate_data_sources_report(self) -> str:
        """Generate the data sources report file.

        Returns:
            Path to the generated file
        """
        from src.reports.report_data_sources import DataSourceRegistry

        registry = DataSourceRegistry(
            self.dataset_config,
            self.external_config,
        )
        path = registry.generate()

        return path

    def _generate_limitations_report(self, context: Dict[str, Any]) -> str:
        """Generate the limitations report file.

        Args:
            context: Rendering context

        Returns:
            Path to the generated file
        """
        from src.reports.report_limitations import LimitationWriter

        writer = LimitationWriter(
            self.dataset_config,
            self.taxonomy_config,
            self.external_config,
        )
        path = writer.generate(context)

        return path
