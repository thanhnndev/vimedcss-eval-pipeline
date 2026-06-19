import os
import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List

from src.icd10_ingestion.schemas import ICD10ErrorRecord

logger = logging.getLogger("icd10_ingestion.reporter")


class ICD10Reporter:
    """Generates markdown ingestion reports from pipeline statistics."""

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        self.report_path = os.path.join(output_dir, "icd10_ingestion_report.md")
        os.makedirs(output_dir, exist_ok=True)

    def generate(
        self,
        record_count: int,
        error_count: int,
        errors: List[ICD10ErrorRecord],
        chapter_stats: Dict[str, int],
        level_stats: Dict[str, int],
        source_url: str = "https://ccs.whiteneuron.com/api/ICD10",
    ) -> str:
        """Generate the markdown ingestion report.

        Args:
            record_count: Total number of records written.
            error_count: Total number of errors encountered.
            errors: List of ICD10ErrorRecord objects.
            chapter_stats: Dict mapping chapter label -> record count.
            level_stats: Dict mapping level -> record count.
            source_url: The API base URL used for ingestion.

        Returns:
            Path to the generated report file.
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        error_rate = (error_count / (record_count + error_count) * 100) if (record_count + error_count) > 0 else 0.0
        join_success_rate = (
            ((record_count - error_count) / record_count * 100)
            if record_count > 0 and error_count <= record_count
            else 100.0
        )

        # Sort chapter stats by chapter code (extract letter)
        def chapter_sort_key(item: tuple) -> tuple:
            label, count = item
            # Extract the Roman numeral or letter prefix for sorting
            return label.split()[0] if label else label

        sorted_chapters = sorted(chapter_stats.items(), key=chapter_sort_key)

        # Error type summary
        error_counter = Counter(e.error_type for e in errors)
        top_errors = error_counter.most_common(5)

        # Build markdown
        lines = [
            "# ICD-10 Dual-Language Ingestion Report",
            "",
            "## Ingestion Metadata",
            "",
            f"| Field | Value |",
            f"| --- | --- |",
            f"| Generated at | {now} |",
            f"| Source | KCB ICD-10 API ({source_url}) |",
            f"| Total records written | {record_count:,} |",
            f"| Total errors | {error_count:,} |",
            f"| Error rate | {error_rate:.2f}% |",
            "",
            "## Chapter Coverage",
            "",
            "| Chapter Label (EN) | Record Count |",
            "| --- | --- |",
        ]

        for chapter_label, count in sorted_chapters:
            lines.append(f"| {chapter_label} | {count:,} |")

        lines.extend([
            "",
            "## Level Distribution",
            "",
            "| Level | Count |",
            "| --- | --- |",
        ])

        level_order = ["chapter", "section", "type", "disease"]
        for level in level_order:
            count = level_stats.get(level, 0)
            lines.append(f"| {level} | {count:,} |")

        lines.extend([
            "",
            "## Error Summary",
            "",
            f"**Total errors:** {error_count:,}",
            "",
            "| Error Type | Count |",
            "| --- | --- |",
        ])

        if top_errors:
            for error_type, count in top_errors:
                lines.append(f"| `{error_type}` | {count:,} |")
        else:
            lines.append("| _(no errors)_ | 0 |")

        if errors:
            lines.extend([
                "",
                "### Top Error Messages (examples)",
                "",
                "| Code | Language | Error Type | Message |",
                "| --- | --- | --- | --- |",
            ])
            for err in errors[:10]:
                msg = err.error_message[:80]
                lines.append(f"| `{err.code}` | {err.language} | `{err.error_type}` | {msg} |")

        lines.extend([
            "",
            "## Data Quality Notes",
            "",
            f"- **Join success rate:** {join_success_rate:.1f}% (EN+VI records joined by `code` field)",
            f"- **Language coverage:** All records have both EN and VI labels when join succeeds.",
            "- **Join key:** Code field only — labels are never matched by text similarity.",
            "- **Error handling:** Failed fetches logged to `icd10_ingestion_errors.csv` with code, language, error_type, and attempt count.",
            "",
            "## Downstream Usage",
            "",
            "This bilingual ICD-10 inventory is consumed by the following phases:",
            "",
            "- **FR1 (Phase 06A):** ICD-10 dual-language ingestion (this pipeline).",
            "- **FR3:** ViMedCSS ICD-10/non-ICD coverage audit — cross-reference ViMedCSS",
            "  transcript terms against the `code` field for disease coverage analysis.",
            "- **FR4:** VietMed feasibility audit — use ICD-10 taxonomy to map disease",
            "  categories across datasets.",
            "",
            "## Files Produced",
            "",
            f"- `data/icd10/icd10_dual_language.jsonl` — {record_count:,} bilingual records (JSONL)",
            f"- `data/icd10/icd10_dual_language.csv` — {record_count:,} bilingual records (CSV)",
            f"- `data/icd10/icd10_ingestion_errors.csv` — {error_count:,} error records",
            "",
        ])

        report_content = "\n".join(lines) + "\n"

        with open(self.report_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        logger.info(f"Report written to {self.report_path}")
        return self.report_path
