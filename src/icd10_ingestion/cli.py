import os
import sys
import json
import time
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import click

from src.shared.logging import setup_logger
from src.icd10_ingestion.fetcher import ICD10Fetcher
from src.icd10_ingestion.parser import ICD10Parser
from src.icd10_ingestion.joiner import ICD10Joiner
from src.icd10_ingestion.reporter import ICD10Reporter
from src.icd10_ingestion.schemas import ICD10Record, ICD10ErrorRecord

logger = setup_logger("icd10_ingestion")


MOCK_CODES = ["I10", "E11", "J18", "K29", "N39"]


def _fetch_code(fetcher: ICD10Fetcher, parser: ICD10Parser, code: str) -> tuple[Dict, Dict]:
    """Fetch and parse a code in both EN and VI. Returns (en_nodes, vi_nodes) dicts."""
    en_response = fetcher.fetch(code, "en")
    en_data = en_response.json()
    en_nodes_raw = parser.parse_response(en_data, "en")

    vi_response = fetcher.fetch(code, "vi")
    vi_data = vi_response.json()
    vi_nodes_raw = parser.parse_response(vi_data, "vi")

    en_dict: Dict[str, any] = {n.code: n for n in en_nodes_raw}
    vi_dict: Dict[str, str] = {}  # code -> label
    for n in vi_nodes_raw:
        vi_dict[n.code] = n.label

    # Reconstruct ParsedNode-like dicts for the joiner
    # The joiner needs ParsedNode objects with code, level, label, parent_code, chapter_code, chapter_label
    from src.icd10_ingestion.parser import ParsedNode

    en_parsed: Dict[str, ParsedNode] = {}
    vi_parsed: Dict[str, ParsedNode] = {}

    for node in en_nodes_raw:
        en_parsed[node.code] = node
    for node in vi_nodes_raw:
        vi_parsed[node.code] = node

    return en_parsed, vi_parsed


def _build_chapter_stats(records: List[ICD10Record]) -> Dict[str, int]:
    """Aggregate record counts per chapter label."""
    from collections import Counter
    counter: Counter[str] = Counter()
    for r in records:
        counter[r.chapter_label_en] += 1
    return dict(counter)


def _build_level_stats(records: List[ICD10Record]) -> Dict[str, int]:
    """Aggregate record counts per level."""
    from collections import Counter
    counter: Counter[str] = Counter()
    for r in records:
        counter[r.level] += 1
    return dict(counter)


def _write_mock_output(output_dir: str, codes: List[str], fetched_at: str) -> int:
    """Write mock JSONL/CSV for the smoke-test codes."""
    mock_jsonl_path = os.path.join(output_dir, "icd10_sample.jsonl")
    mock_csv_path = os.path.join(output_dir, "icd10_sample.csv")

    records: List[ICD10Record] = []
    for code in codes:
        records.append(
            ICD10Record(
                code=code,
                level="type",
                label_en=f"Mock EN label for {code}",
                label_vi=f"Nhãn VI giả cho {code}",
                chapter_code="IX",
                chapter_label_en=f"Chapter IX (mock)",
                chapter_label_vi=f"Chương IX (giả)",
                parent_code=None,
                source="kcb_icd10_tt06",
                source_url=f"https://ccs.whiteneuron.com/api/ICD10/search/{code}?lang=en&vol1=1&vol3=0&html=true",
                fetched_at=fetched_at,
            )
        )

    # Write JSONL
    with open(mock_jsonl_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec.model_dump(), ensure_ascii=False) + "\n")

    # Write CSV
    import csv

    with open(mock_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "code", "level", "label_en", "label_vi", "chapter_code",
                "chapter_label_en", "chapter_label_vi", "parent_code",
                "source", "source_url", "fetched_at",
            ],
        )
        writer.writeheader()
        for rec in records:
            writer.writerow(rec.model_dump())

    logger.info(f"Mock output written: {mock_jsonl_path}, {mock_csv_path}")
    return len(records)


@click.command()
@click.option("--mock", is_flag=True, help="Smoke test: fetch only 5 known codes (I10, E11, J18, K29, N39)")
@click.option("--full", is_flag=True, help="Full ingestion: all ~27,104 ICD-10 codes")
@click.option("--resume", is_flag=True, help="Resume from last failure (reads progress file)")
@click.option("--dry-run", is_flag=True, help="Print code list without making API calls")
@click.option("--output", default="data/icd10", help="Output directory")
@click.option("--code-list", type=click.Path(exists=True), default=None, help="Custom code list file (one code per line)")
@click.option("--progress-file", default=None, help="Override progress file path (default: {output}/.progress.json)")
def run(
    mock: bool,
    full: bool,
    resume: bool,
    dry_run: bool,
    output: str,
    code_list: Optional[str],
    progress_file: Optional[str],
):
    """ICD-10 dual-language ingestion CLI.

    Fetches ICD-10 codes from the KCB API in English and Vietnamese,
    joins by code, and writes JSONL + CSV outputs with a markdown report.
    """
    # Progress file
    if progress_file is None:
        progress_file = os.path.join(output, ".progress.json")

    now = datetime.now(timezone.utc).isoformat()

    # --dry-run: print code list without API calls
    if dry_run:
        logger.info("Dry-run mode: printing code list without making API calls")
        joiner = ICD10Joiner(output_dir=output)
        codes = joiner.build_code_list()
        print(f"Total ICD-10 codes: {len(codes):,}")
        print("First 10 codes:")
        for code in codes[:10]:
            print(f"  {code}")
        print("Last 10 codes:")
        for code in codes[-10:]:
            print(f"  {code}")
        return

    # Determine mode
    if not (mock or full or resume):
        logger.error("Please specify --mock, --full, or --resume")
        click.echo("Error: specify --mock, --full, or --resume", err=True)
        sys.exit(1)

    # --mock mode
    if mock:
        logger.info("Mock mode: smoke testing with 5 codes")
        click.echo(f"Running mock ingestion with codes: {MOCK_CODES}")

        os.makedirs(output, exist_ok=True)
        fetcher = ICD10Fetcher(rate_limit_ms=100)
        parser = ICD10Parser()

        fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        en_parsed: Dict[str, any] = {}
        vi_parsed: Dict[str, any] = {}
        all_errors: List[ICD10ErrorRecord] = []

        for code in MOCK_CODES:
            try:
                en_nodes = parser.parse_response(fetcher.fetch(code, "en").json(), "en")
                vi_nodes = parser.parse_response(fetcher.fetch(code, "vi").json(), "vi")
                for n in en_nodes:
                    en_parsed[n.code] = n
                for n in vi_nodes:
                    vi_parsed[n.code] = n
            except Exception as exc:
                logger.error(f"Failed to fetch {code}: {exc}")
                all_errors.append(
                    ICD10ErrorRecord(
                        code=code,
                        language="en",
                        error_type="http_error",
                        error_message=str(exc),
                        attempt=1,
                        timestamp=fetched_at,
                    )
                )

        # Write output via joiner
        joiner = ICD10Joiner(output_dir=output)
        record_count = joiner.run(en_parsed, vi_parsed, fetched_at)
        all_errors.extend(joiner.errors)

        # Write mock-specific output files
        n_written = _write_mock_output(output, MOCK_CODES, fetched_at)

        # Generate report
        report = ICD10Reporter(output_dir="reports")
        report.generate(
            record_count=n_written,
            error_count=len(all_errors),
            errors=all_errors,
            chapter_stats={},
            level_stats={},
        )

        fetcher.close()
        click.echo(f"Mock ingestion complete: {n_written} records written to {output}")
        return

    # --resume mode: load progress
    start_index = 0
    if resume:
        if os.path.exists(progress_file):
            with open(progress_file, "r") as f:
                progress = json.load(f)
                start_index = progress.get("last_processed_index", 0)
            click.echo(f"Resuming from index {start_index} (read from {progress_file})")
        else:
            click.echo(f"No progress file found at {progress_file}; starting from beginning")
            start_index = 0

    # --full mode: build code list
    joiner = ICD10Joiner(output_dir=output)
    if code_list:
        with open(code_list, "r") as f:
            codes = [line.strip() for line in f if line.strip()]
        click.echo(f"Loaded {len(codes):,} codes from {code_list}")
    else:
        codes = joiner.build_code_list()
        click.echo(f"Built code list: {len(codes):,} total codes")

    codes_to_process = codes[start_index:]
    click.echo(f"Processing {len(codes_to_process):,} codes (starting from index {start_index})")

    fetcher = ICD10Fetcher(rate_limit_ms=200)
    parser = ICD10Parser()
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Track parsed results
    en_parsed: Dict[str, any] = {}
    vi_parsed: Dict[str, any] = {}
    all_errors: List[ICD10ErrorRecord] = []
    total = len(codes_to_process)

    for i, code in enumerate(codes_to_process):
        idx = start_index + i + 1
        try:
            # Fetch EN
            en_nodes = parser.parse_response(fetcher.fetch(code, "en").json(), "en")
            for n in en_nodes:
                en_parsed[n.code] = n
            # Fetch VI
            vi_nodes = parser.parse_response(fetcher.fetch(code, "vi").json(), "vi")
            for n in vi_nodes:
                vi_parsed[n.code] = n
        except Exception as exc:
            logger.warning(f"Failed to fetch {code}: {exc}")
            all_errors.append(
                ICD10ErrorRecord(
                    code=code,
                    language="en",
                    error_type="http_error",
                    error_message=str(exc),
                    attempt=1,
                    timestamp=fetched_at,
                )
            )

        # Progress every 100 codes
        if (i + 1) % 100 == 0 or (i + 1) == total:
            pct = (i + 1) / total * 100
            click.echo(f"Progress: {idx}/{total} ({pct:.1f}%) -- errors: {len(all_errors)}")

            # Save progress
            os.makedirs(os.path.dirname(progress_file) or ".", exist_ok=True)
            with open(progress_file, "w") as f:
                json.dump({"last_processed_index": idx, "last_code": code}, f)

    # Write final output
    click.echo("Writing output files...")
    record_count = joiner.run(en_parsed, vi_parsed, fetched_at)
    all_errors.extend(joiner.errors)

    # Compute stats from records
    jsonl_path = joiner.jsonl_path
    written_records: List[ICD10Record] = []
    if os.path.exists(jsonl_path):
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    written_records.append(ICD10Record(**data))
                except Exception:
                    pass

    chapter_stats = _build_chapter_stats(written_records)
    level_stats = _build_level_stats(written_records)

    # Generate report
    report = ICD10Reporter(output_dir="reports")
    report.generate(
        record_count=record_count,
        error_count=len(all_errors),
        errors=all_errors,
        chapter_stats=chapter_stats,
        level_stats=level_stats,
    )

    fetcher.close()

    error_rate = len(all_errors) / total * 100 if total > 0 else 0.0
    click.echo(
        f"Full ingestion complete: {record_count} records, "
        f"{len(all_errors)} errors ({error_rate:.1f}%)"
    )


if __name__ == "__main__":
    run()
