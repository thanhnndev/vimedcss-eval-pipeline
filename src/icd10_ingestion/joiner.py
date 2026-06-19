import os
import csv
import json
import logging
from typing import Dict, List, Set

from src.icd10_ingestion.schemas import ICD10Record, ICD10ErrorRecord
from src.icd10_ingestion.parser import ParsedNode

logger = logging.getLogger("icd10_ingestion.joiner")

# WHO ICD-10 Volume 1 tabular list ranges
_ICD10_RANGES: List[tuple[str, str]] = [
    ("A00", "A79"),
    ("A80", "B99"),
    ("C00", "D48"),
    ("D50", "D89"),
    ("E00", "E90"),
    ("F00", "F99"),
    ("G00", "G99"),
    ("H00", "H59"),
    ("H60", "H95"),
    ("I00", "I99"),
    ("J00", "J99"),
    ("K00", "K93"),
    ("L00", "L99"),
    ("M00", "M99"),
    ("N00", "N99"),
    ("O00", "O99"),
    ("P00", "P96"),
    ("Q00", "Q99"),
    ("R00", "R99"),
    ("S00", "T98"),
    ("V01", "Y98"),
    ("Z00", "Z99"),
]

_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _generate_3char_codes() -> Set[str]:
    """Generate all valid 3-char ICD-10 category codes within WHO ranges.

    Iterates over each range tuple (start, end) and generates codes only
    within that letter/number boundary, e.g. A00-A79, C00-D48, etc.
    """
    codes: Set[str] = set()
    for start, end in _ICD10_RANGES:
        s_letter, s_num = start[0], start[1:]
        e_letter, e_num = end[0], end[1:]
        for letter in _LETTERS:
            if letter < s_letter or letter > e_letter:
                continue
            for hi in range(10):
                for lo in range(10):
                    num = f"{hi}{lo}"
                    # Skip numbers outside the letter's range boundary
                    if letter == s_letter and num < s_num:
                        continue
                    if letter == e_letter and num > e_num:
                        continue
                    codes.add(f"{letter}{num}")
    return codes


def _generate_4char_codes(three_char_codes: Set[str]) -> List[str]:
    """Generate 4-char subcodes for each 3-char code (e.g., A00.0, A00.1, ... A00.9)."""
    codes: List[str] = []
    for base in sorted(three_char_codes):
        for sub in range(10):
            codes.append(f"{base}.{sub}")
    return codes


class ICD10Joiner:
    """Joins EN/VI parsed records by code and writes JSONL/CSV output."""

    CSV_FIELDNAMES = [
        "code", "level", "label_en", "label_vi", "chapter_code",
        "chapter_label_en", "chapter_label_vi", "parent_code",
        "source", "source_url", "fetched_at",
    ]

    def __init__(self, output_dir: str = "data/icd10"):
        self.output_dir = output_dir
        self.errors: List[ICD10ErrorRecord] = []
        self.jsonl_path = os.path.join(output_dir, "icd10_dual_language.jsonl")
        self.csv_path = os.path.join(output_dir, "icd10_dual_language.csv")
        self.error_csv_path = os.path.join(output_dir, "icd10_ingestion_errors.csv")
        os.makedirs(output_dir, exist_ok=True)

    def build_code_list(self) -> List[str]:
        """Build the complete ICD-10 code list: all 3-char + 4-char codes."""
        three_char = _generate_3char_codes()
        four_char = _generate_4char_codes(three_char)
        # Build a set of 4-char prefixes for fast prefix lookup
        four_prefixes: Set[str] = {c[:3] for c in four_char}
        # 3-char codes that have 4-char subcodes go first, then 3-char only
        three_sorted = sorted(three_char)
        three_with_subs = [c for c in three_sorted if c in four_prefixes]
        three_alone = [c for c in three_sorted if c not in four_prefixes]
        # 4-char sorted alphabetically (A00.0 before A00, etc.)
        four_sorted = sorted(four_char)
        # For each 3-char with subcodes, interleave its 4-char children after it
        all_codes: List[str] = []
        for three_code in three_sorted:
            if three_code in four_prefixes:
                all_codes.append(three_code)
                all_codes.extend(c for c in four_sorted if c.startswith(three_code + "."))
            else:
                all_codes.append(three_code)
        return all_codes

    def run(
        self,
        fetched_en: Dict[str, ParsedNode],
        fetched_vi: Dict[str, ParsedNode],
        fetched_at: str,
    ) -> int:
        """Join EN and VI records by code and write JSONL + CSV incrementally.

        Args:
            fetched_en: Dict mapping code -> ParsedNode from EN responses.
            fetched_vi: Dict mapping code -> ParsedNode from VI responses.
            fetched_at: ISO 8601 timestamp for all records.

        Returns:
            Total number of records written.
        """
        all_codes = set(fetched_en.keys()) | set(fetched_vi.keys())
        logger.info(f"Joining {len(all_codes)} unique codes (EN={len(fetched_en)}, VI={len(fetched_vi)})")

        jsonl_file = open(self.jsonl_path, "w", encoding="utf-8")
        csv_file = open(self.csv_path, "w", newline="", encoding="utf-8")
        csv_writer = csv.DictWriter(csv_file, fieldnames=self.CSV_FIELDNAMES)
        csv_writer.writeheader()

        record_count = 0
        flushed = 0

        for code in sorted(all_codes):
            en_node = fetched_en.get(code)
            vi_node = fetched_vi.get(code)

            if en_node and vi_node:
                # Both languages available — normal join
                record = ICD10Record(
                    code=en_node.code,
                    level=en_node.level,
                    label_en=en_node.label,
                    label_vi=vi_node.label,
                    chapter_code=en_node.chapter_code,
                    chapter_label_en=en_node.chapter_label,
                    chapter_label_vi=vi_node.chapter_label,
                    parent_code=en_node.parent_code,
                    source="kcb_icd10_tt06",
                    source_url=f"https://ccs.whiteneuron.com/api/ICD10/search/{code}",
                    fetched_at=fetched_at,
                )
            elif en_node and not vi_node:
                # EN only
                self.errors.append(
                    ICD10ErrorRecord(
                        code=code,
                        language="vi",
                        error_type="missing_language",
                        error_message="VI label not found for this code",
                        attempt=1,
                        timestamp=fetched_at,
                    )
                )
                record = ICD10Record(
                    code=en_node.code,
                    level=en_node.level,
                    label_en=en_node.label,
                    label_vi="",
                    chapter_code=en_node.chapter_code,
                    chapter_label_en=en_node.chapter_label,
                    chapter_label_vi="",
                    parent_code=en_node.parent_code,
                    source="kcb_icd10_tt06",
                    source_url=f"https://ccs.whiteneuron.com/api/ICD10/search/{code}",
                    fetched_at=fetched_at,
                )
            elif vi_node and not en_node:
                # VI only
                self.errors.append(
                    ICD10ErrorRecord(
                        code=code,
                        language="en",
                        error_type="missing_language",
                        error_message="EN label not found for this code",
                        attempt=1,
                        timestamp=fetched_at,
                    )
                )
                record = ICD10Record(
                    code=vi_node.code,
                    level=vi_node.level,
                    label_en="",
                    label_vi=vi_node.label,
                    chapter_code=vi_node.chapter_code,
                    chapter_label_en="",
                    chapter_label_vi=vi_node.chapter_label,
                    parent_code=vi_node.parent_code,
                    source="kcb_icd10_tt06",
                    source_url=f"https://ccs.whiteneuron.com/api/ICD10/search/{code}",
                    fetched_at=fetched_at,
                )
            else:
                continue

            # Write to JSONL
            jsonl_file.write(json.dumps(record.model_dump(), ensure_ascii=False) + "\n")

            # Write to CSV
            csv_writer.writerow(record.model_dump())

            record_count += 1

            # Flush every 100 records
            if record_count % 100 == 0:
                jsonl_file.flush()
                csv_file.flush()
                flushed += 1

        jsonl_file.close()
        csv_file.close()

        # Write error CSV
        self._write_error_csv()

        logger.info(
            f"Wrote {record_count} records to {self.jsonl_path} and {self.csv_path} "
            f"({flushed} flushes, {len(self.errors)} errors)"
        )
        return record_count

    def _write_error_csv(self) -> None:
        """Write collected errors to the error CSV file."""
        if not self.errors:
            # Write empty file with headers
            with open(self.error_csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["code", "language", "error_type", "error_message", "attempt", "timestamp"],
                )
                writer.writeheader()
            return

        with open(self.error_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["code", "language", "error_type", "error_message", "attempt", "timestamp"],
            )
            writer.writeheader()
            for err in self.errors:
                writer.writerow(err.model_dump())
        logger.info(f"Wrote {len(self.errors)} errors to {self.error_csv_path}")
