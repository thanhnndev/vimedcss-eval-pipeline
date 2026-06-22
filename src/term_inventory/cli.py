"""Phase 6b: CLI entry point for medical term inventory build.

Usage:
    python -m src.term_inventory.cli build-inventory [--mock] [--full] [--output-dir DIR] [--limit N]

The build-inventory subcommand orchestrates all loaders, concatenates their
output, and writes medical_term_inventory.csv to the output directory.

Flags:
    --mock: use small seed lists for smoke tests (rxnorm_drug_list_mock).
    --full: use full seed lists from config (default).
    --output-dir: override the output directory path.
    --limit N: limit number of terms loaded per source (for smoke tests).
"""
from __future__ import annotations

import argparse
import os
import sys

import yaml

# Ensure project root is on path for 'src.' imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.shared.logging import setup_logger
from src.term_inventory.loaders import Icd10BackboneLoader, RxNormLoader
from src.term_inventory.schemas import InventoryConfig

logger = setup_logger("term_inventory.cli")


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the term-inventory CLI.

    Returns:
        Configured ArgumentParser with 'build-inventory' subcommand.
    """
    parser = argparse.ArgumentParser(
        prog="python -m src.term_inventory.cli",
        description="Phase 6b: Medical Term Inventory CLI — build multi-source term inventory"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    build_parser = subparsers.add_parser(
        "build-inventory",
        help="Build the medical term inventory from all configured sources"
    )
    build_parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock/small seed lists (smoke test mode)"
    )
    build_parser.add_argument(
        "--full",
        action="store_true",
        help="Use full seed lists from config (default)"
    )
    build_parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Override output directory (default: from config or data/terms)"
    )
    build_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of terms per source (for smoke tests)"
    )
    build_parser.add_argument(
        "--config",
        type=str,
        default="configs/term_inventory.yaml",
        help="Path to term_inventory.yaml config (default: configs/term_inventory.yaml)"
    )

    return parser


def _load_config(config_path: str, use_mock: bool = False) -> InventoryConfig:
    """Load InventoryConfig from YAML, applying --mock overrides.

    Args:
        config_path: path to configs/term_inventory.yaml
        use_mock: if True, replace rxnorm_drug_list with rxnorm_drug_list_mock

    Returns:
        InventoryConfig instance
    """
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    else:
        logger.warning(f"Config file not found: {config_path} — using defaults")
        raw = {}

    if use_mock:
        mock_drug_list = raw.get("rxnorm_drug_list_mock", ["metformin", "insulin", "aspirin"])
        raw["rxnorm_drug_list"] = mock_drug_list
        logger.info(f"Mock mode: using {len(mock_drug_list)} seed drug names per source")

    try:
        config = InventoryConfig.model_validate(raw)
    except Exception as e:
        logger.error(f"Failed to validate config: {e}")
        raise
    return config


def run_build_inventory(args: argparse.Namespace) -> None:
    """Execute the inventory build pipeline.

    Args:
        args: parsed arguments from build_arg_parser()
    """
    # Load config
    config = _load_config(args.config, use_mock=args.mock)

    # Override output dir from CLI if provided
    output_dir = args.output_dir or config.output_dir
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "medical_term_inventory.csv")

    # Collect DataFrames from all loaders
    all_dfs: list[dict] = []
    sources_loaded = 0

    # --- ICD-10 Backbone ---
    logger.info("Loading ICD-10 backbone...")
    try:
        icd10_loader = Icd10BackboneLoader(config)
        icd10_df = icd10_loader.load()
        if not icd10_df.empty:
            if args.limit:
                icd10_df = icd10_df.head(args.limit)
            all_dfs.append({"source": "icd10", "count": len(icd10_df), "df": icd10_df})
            sources_loaded += 1
            logger.info(f"ICD-10: loaded {len(icd10_df)} disease terms")
        else:
            logger.warning("ICD-10 backbone returned 0 rows")
    except FileNotFoundError as e:
        logger.warning(f"ICD-10 backbone skipped: {e}")
    except Exception as e:
        logger.error(f"ICD-10 backbone failed: {e}")

    # --- RxNorm Drug Loader ---
    logger.info("Loading RxNorm drugs...")
    try:
        rxnorm_loader = RxNormLoader(config)
        rxnorm_df = rxnorm_loader.load()
        if not rxnorm_df.empty:
            if args.limit:
                rxnorm_df = rxnorm_df.head(args.limit)
            all_dfs.append({"source": "rxnorm", "count": len(rxnorm_df), "df": rxnorm_df})
            sources_loaded += 1
            logger.info(f"RxNorm: loaded {len(rxnorm_df)} drug terms")
        else:
            logger.warning("RxNorm returned 0 rows (check network connectivity)")
    except Exception as e:
        logger.error(f"RxNorm loader failed: {e}")

    # --- Concatenate and save ---
    if not all_dfs:
        logger.error("No data loaded from any source — inventory not written")
        return

    import pandas as pd
    combined_df = pd.concat([item["df"] for item in all_dfs], ignore_index=True)

    combined_df.to_csv(output_path, index=False)
    total_terms = len(combined_df)

    # Summary output
    summary_lines = [
        f"Loaded {total_terms} terms from {sources_loaded} source(s)",
        f"Output: {output_path}",
    ]
    for item in all_dfs:
        summary_lines.append(f"  - {item['source']}: {item['count']} terms")

    logger.info("Build complete!")
    for line in summary_lines:
        print(line)


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "build-inventory":
        run_build_inventory(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
