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
from src.term_inventory.schemas import InventoryConfig
from src.term_inventory.builder import InventoryBuilder

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
    """Execute the inventory build pipeline using InventoryBuilder.

    Args:
        args: parsed arguments from build_arg_parser()
    """
    # Load config with --mock overrides applied
    config = _load_config(args.config, use_mock=args.mock)

    # Override output dir from CLI if provided
    if args.output_dir:
        config.output_dir = args.output_dir

    # Create builder
    builder = InventoryBuilder(config)

    # Run the full pipeline
    stats = builder.build(mock=args.mock, limit=args.limit)

    # Print summary table
    print("\n" + "=" * 60)
    print("Medical Term Inventory Build Complete")
    print("=" * 60)
    print(f"Total terms:          {stats['total_terms']:,}")
    print(f"Authoritative:         {stats['authoritative_count']:,}")
    print(f"LLM candidates:        {stats['llm_candidate_count']:,}")
    print(f"Review queue:          {stats['review_queue_count']:,}")
    print(f"Normalization map:     {stats['normalization_map_count']:,} transformations")
    print(f"Elapsed:               {stats.get('elapsed_seconds', 'N/A')}s")
    print("=" * 60)
    print(f"Output directory:      {config.output_dir}/")
    print(f"  - medical_term_inventory.csv")
    print(f"  - term_normalization_map.csv")
    print(f"  - human_review_terms.csv")
    print(f"  - term_sources.csv")
    print(f"Report:                reports/term_inventory_report.md")


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
