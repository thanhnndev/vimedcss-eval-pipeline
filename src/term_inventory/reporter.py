"""Term inventory report generator for Phase 6b.

Generates `reports/term_inventory_report.md` with:
- Summary statistics table
- Entity type distribution
- Source distribution
- Verification status breakdown
- Normalization statistics
- Vietnamese narrative explanation
"""
import os
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from src.shared.logging import setup_logger

logger = setup_logger("term_inventory.reporter")

_REPORT_DIR = "reports"


def generate_term_inventory_report(
    inventory_df: pd.DataFrame,
    norm_map_df: pd.DataFrame,
) -> dict[str, Any]:
    """Generate the term inventory report and compute summary statistics.

    Writes `reports/term_inventory_report.md` and returns a stats dict.

    Args:
        inventory_df: The classified term inventory DataFrame.
        norm_map_df: The normalization map DataFrame.

    Returns:
        Dict with total_terms, authoritative_count, llm_candidate_count,
        review_queue_count, entity_type_distribution, source_distribution,
        normalization_map_count, deduplication_count.
    """
    os.makedirs(_REPORT_DIR, exist_ok=True)
    report_path = os.path.join(_REPORT_DIR, "term_inventory_report.md")

    # ---- Compute statistics ----
    total_terms = len(inventory_df)

    # Authoritative vs LLM-classified
    AUTHORITATIVE_SOURCES = {"icd10", "rxnorm", "openfda"}

    authoritative_count = 0
    llm_candidate_count = 0
    review_queue_count = 0
    entity_type_dist: dict[str, int] = {}
    source_dist: dict[str, int] = {}
    verification_dist: dict[str, int] = {}

    if total_terms > 0 and len(inventory_df.columns) > 0:
        source_col = inventory_df["source_name"].astype(str).str.strip().str.lower()
        authoritative_mask = source_col.isin([s.lower() for s in AUTHORITATIVE_SOURCES])
        authoritative_count = int(authoritative_mask.sum())
        llm_candidate_count = total_terms - authoritative_count

        # Review queue
        review_status_str = (
            inventory_df["review_status"]
            .astype(str)
            .str.strip()
            .str.lower()
        )
        llm_candidate_str = (
            inventory_df["llm_generated_candidate"]
            .astype(str)
            .str.strip()
            .str.lower()
        )
        review_queue_mask = (
            review_status_str.isin(["not_verified", "needs_review"])
            | (llm_candidate_str == "true")
        )
        review_queue_count = int(review_queue_mask.sum())

        # Entity type distribution
        if "entity_type" in inventory_df.columns:
            entity_type_dist = (
                inventory_df["entity_type"]
                .astype(str)
                .str.strip()
                .str.lower()
                .value_counts()
                .to_dict()
            )

        # Source distribution
        if "source_name" in inventory_df.columns:
            source_dist = (
                inventory_df["source_name"]
                .astype(str)
                .str.strip()
                .str.lower()
                .value_counts()
                .to_dict()
            )

        # Verification status distribution
        if "review_status" in inventory_df.columns:
            verification_dist = (
                inventory_df["review_status"]
                .astype(str)
                .str.strip()
                .str.lower()
                .value_counts()
                .to_dict()
            )

    # Normalization stats
    normalization_map_count = len(norm_map_df)
    normalization_rate = (
        100 * normalization_map_count / max(total_terms, 1)
    )

    # ---- Build markdown report ----
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = [
        "# Medical Term Inventory Report",
        "",
        f"**Generated:** {now}",
        f"**Pipeline:** Phase 6b — Medical Term Inventory Extended",
        "",
        "---",
        "",
        "## Tóm tắt tổng quan (Summary)",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Tổng số thuật ngữ (Total terms) | {total_terms:,} |",
        f"| Nguồn có thẩm quyền (Authoritative) | {authoritative_count:,} |",
        f"| Ứng viên LLM (LLM candidates) | {llm_candidate_count:,} |",
        f"| Cần xem xét thủ công (Review queue) | {review_queue_count:,} |",
        f"| Số dạng biến đổi chuẩn hóa (Normalization transformations) | {normalization_map_count:,} ({normalization_rate:.1f}%) |",
        "",
        "---",
        "",
        "## Phân bố loại thực thể (Entity Type Distribution)",
        "",
    ]

    if entity_type_dist:
        lines += [
            "| Entity Type | Count | % |",
            "| --- | ---: | ---: |",
        ]
        for etype, count in sorted(entity_type_dist.items(), key=lambda x: -x[1]):
            pct = 100 * count / max(total_terms, 1)
            lines.append(f"| {etype} | {count:,} | {pct:.1f}% |")
    else:
        lines.append("_No entity type data available._")

    lines += [
        "",
        "---",
        "",
        "## Phân bố nguồn (Source Distribution)",
        "",
    ]

    if source_dist:
        lines += [
            "| Source | Terms | % | Authoritative |",
            "| --- | ---: | ---: | ---: |",
        ]
        for src, count in sorted(source_dist.items(), key=lambda x: -x[1]):
            is_auth = src in AUTHORITATIVE_SOURCES
            pct = 100 * count / max(total_terms, 1)
            lines.append(f"| {src} | {count:,} | {pct:.1f}% | {'✓' if is_auth else '—'} |")
    else:
        lines.append("_No source data available._")

    lines += [
        "",
        "---",
        "",
        "## Trạng thái xác minh (Verification Status)",
        "",
    ]

    if verification_dist:
        lines += [
            "| Status | Count | % |",
            "| --- | ---: | ---: |",
        ]
        for status, count in sorted(verification_dist.items(), key=lambda x: -x[1]):
            pct = 100 * count / max(total_terms, 1)
            status_label = {
                "verified": "Đã xác minh (Verified)",
                "llm_candidate": "Ứng viên LLM",
                "not_verified": "Chưa xác minh (Not verified)",
                "needs_review": "Cần xem xét (Needs review)",
            }.get(status, status)
            lines.append(f"| {status_label} | {count:,} | {pct:.1f}% |")
    else:
        lines.append("_No verification status data available._")

    lines += [
        "",
        "---",
        "",
        "## Thống kê chuẩn hóa (Normalization Statistics)",
        "",
        f"- **Tổng số biến đổi chuẩn hóa:** {normalization_map_count}",
        f"- **Tỷ lệ chuẩn hóa:** {normalization_rate:.1f}%",
        f"- **Tổng số thuật ngữ đầu vào:** {total_terms}",
        "",
        "Các dạng biến đổi bao gồm: NFC unicode, Greek→ASCII, case folding, "
        "unit suffix normalization, dấu câu, và whitespace.",
        "",
        "---",
        "",
        "## Giải thích bằng tiếng Việt (Vietnamese Narrative)",
        "",
        "### Tổng quan",
        "",
        f"Báo cáo này ghi nhận **{total_terms:,} thuật ngữ y tế** được thu thập từ "
        f"**{len(source_dist)} nguồn** khác nhau, bao gồm ICD-10, RxNorm, openFDA, "
        "NLM Lab Tests, danh sách viết tắt y tế, và thuật ngữ từ bộ dữ liệu ViMedCSS.",
        "",
        f"Trong đó, **{authoritative_count:,} thuật ngữ** đến từ các nguồn có thẩm "
        "quyền (ICD-10, RxNorm, openFDA) và đã được xác minh. "
        f"**{llm_candidate_count:,} thuật ngữ** được phân loại bởi mô hình ngôn ngữ lớn (LLM).",
        "",
        f"**{review_queue_count:,} thuật ngữ** cần được xem xét thủ công trước khi "
        "đưa vào kho thuật ngữ chính thức.",
        "",
        "### Phân loại theo loại thực thể",
        "",
        "Các loại thực thể bao gồm: disease (bệnh), drug (thuốc), lab_test (xét nghiệm), "
        "procedure (thủ thuật), anatomy (giải phẫu), symptom (triệu chứng), "
        "abbreviation (viết tắt), hormone, biomarker, pathogen, device (thiết bị), "
        "unit (đơn vị), dosage (liều lượng), và unknown (không xác định).",
        "",
        "### Tiếp theo",
        "",
        "1. **Xem xét thủ công:** Duyệt danh sách `human_review_terms.csv` "
        "để xác minh các thuật ngữ LLM.",
        "",
        "2. **Mở rộng nguồn:** Bổ sung thêm nguồn thuật ngữ từ UMLS, SNOMED CT, "
        "hoặc các cơ sở dữ liệu y tế khác.",
        "",
        "3. **Đánh giá ASR:** Sử dụng kho thuật ngữ này để đánh giá khả năng "
        "nhận dạng thuật ngữ y tế của các mô hình ASR trong Phase 4.",
        "",
        "---",
        "",
        f"_Report generated by Phase 6b InventoryBuilder — {now}_",
    ]

    report_content = "\n".join(lines)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    logger.info(f"Report written: {report_path}")

    return {
        "total_terms": total_terms,
        "authoritative_count": authoritative_count,
        "llm_candidate_count": llm_candidate_count,
        "review_queue_count": review_queue_count,
        "entity_type_distribution": entity_type_dist,
        "source_distribution": source_dist,
        "verification_dist": verification_dist,
        "normalization_map_count": normalization_map_count,
    }
