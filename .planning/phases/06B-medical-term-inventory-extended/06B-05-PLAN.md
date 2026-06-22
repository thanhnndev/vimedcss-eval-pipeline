---
phase: "06B"
plan: "05"
type: execute
wave: 4
depends_on: ["06B-02", "06B-03", "06B-04"]
files_modified:
  - "src/term_inventory/builder.py"
  - "src/term_inventory/cli.py"
  - "src/term_inventory/reporter.py"
autonomous: true
requirements:
  - "FR2-03"
  - "FR2-04"
  - "FR2-05"
  - "FR2-06"
---

<objective>
Build the `InventoryBuilder` orchestrator that wires all loaders, normalization, deduplication, LLM classification, and CSV export together into a single pipeline. This plan delivers the complete working pipeline with all four output files: `medical_term_inventory.csv`, `term_sources.csv`, `term_normalization_map.csv`, and `human_review_terms.csv`.

Purpose: The orchestrator is what makes Phase 6b actionable. Each loader, normalizer, and classifier is useful in isolation, but the builder produces the actual deliverables.
Output: `data/terms/medical_term_inventory.csv`, `data/terms/term_sources.csv`, `data/terms/term_normalization_map.csv`, `data/terms/human_review_terms.csv`, `reports/term_inventory_report.md`.
</objective>

<execution_context>
@$HOME/.cursor/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@src/term_inventory/schemas.py
@src/term_inventory/loaders/icd10_backbone.py
@src/term_inventory/loaders/rxnorm_loader.py
@src/term_inventory/loaders/nlm_lab_loader.py
@src/term_inventory/loaders/openfda_device_loader.py
@src/term_inventory/loaders/abbreviation_loader.py
@src/term_inventory/loaders/vimedcss_seed_loader.py
@src/term_inventory/normalizer.py
@src/term_inventory/classifier.py
@.planning/phases/06B-medical-term-inventory-extended/06B-01-PLAN.md
@.planning/phases/06B-medical-term-inventory-extended/06B-02-PLAN.md
@.planning/phases/06B-medical-term-inventory-extended/06B-03-PLAN.md
@.planning/phases/06B-medical-term-inventory-extended/06B-04-PLAN.md

## Pipeline Order (from Research Architecture Diagram)

1. Load all sources → concat DataFrames
2. Apply normalization → term_normalized column + normalization_map
3. Deduplicate within entity_type → deduplication_map
4. LLM classify non-authoritative terms → entity_type + medical_domain
5. Export 4 CSV files + report

## Output Files Schema

1. `data/terms/medical_term_inventory.csv`:
   - term_id, term_original, term_normalized, entity_type, medical_domain, source_name, source_url, source_license, icd10_code, rxnorm_rxcui, is_code_switch_candidate, review_status, llm_generated_candidate, fetched_at

2. `data/terms/term_sources.csv`:
   - source_name, source_url, source_license, entity_types_provided, term_count, authoritative

3. `data/terms/term_normalization_map.csv`:
   - raw_form, normalized_form, transformation, entity_type, term_id

4. `data/terms/human_review_terms.csv`:
   - term_id, term_original, term_normalized, entity_type, medical_domain, source_name, review_status, llm_generated_candidate, needs_human_review_reason

## CLI Integration

The `build-inventory` CLI command (Plan 01) calls `InventoryBuilder.build()` internally.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Implement InventoryBuilder orchestrator</name>
  <files>src/term_inventory/builder.py</files>
  <read_first>src/term_inventory/normalizer.py</read_first>
  <action>
Create `src/term_inventory/builder.py`:

```python
"""Phase 6b InventoryBuilder — orchestrates the full term inventory pipeline.

Pipeline order:
  1. Load all sources via their loaders
  2. Concatenate into unified DataFrame
  3. Assign term_id to each row
  4. Apply normalization (term_normalized + normalization_map)
  5. Deduplicate within entity_type
  6. LLM classify non-authoritative terms
  7. Export 4 CSV files + report
"""
import os
import time
import pandas as pd
from typing import Dict, Any
from src.term_inventory.schemas import InventoryConfig
from src.term_inventory.loaders import (
    Icd10BackboneLoader,
    RxNormLoader,
    NlmLabLoader,
    OpenFdaDeviceLoader,
    AbbreviationLoader,
    VimedcssSeedLoader,
)
from src.term_inventory.normalizer import apply_normalization, deduplicate_within_entity_type
from src.term_inventory.classifier import MedicalTermClassifier
from src.term_inventory.reporter import generate_term_inventory_report
from src.shared.logging import setup_logger

logger = setup_logger("term_inventory.builder")
```

Implement `InventoryBuilder`:

1. `__init__(self, config: InventoryConfig)`:
   - Store config
   - Create all loaders
   - Initialize normalizer
   - Initialize classifier

2. `build(mock: bool = False, limit: int = None) -> Dict[str, Any]`:
   - `t0 = time.time()`
   - `os.makedirs(config.output_dir, exist_ok=True)`
   - Step 1: Load all sources in parallel (no dependencies between loaders):
     ```python
     logger.info("Loading sources...")
     icd10_df = self.icd10_loader.load()
     rxnorm_df = self.rxnorm_loader.load()
     nlm_df = self.nlm_lab_loader.load()
     openfda_df = self.openfda_loader.load()
     abbrev_df = self.abbreviation_loader.load()
     seed_df = self.vimedcss_seed_loader.load()
     ```
   - If `mock=True`: truncate each DataFrame to `min(len(df), limit or 5)`
   - If `limit` set: truncate to that many rows
   - Step 2: Concatenate all DataFrames:
     ```python
     combined_df = pd.concat([icd10_df, rxnorm_df, nlm_df, openfda_df, abbrev_df, seed_df], ignore_index=True)
     ```
   - Step 3: Assign `term_id` as `f"term_{i:06d}"` (zero-padded)
   - Step 4: Apply normalization — call `apply_normalization(combined_df)`:
     ```python
     normalized_df, norm_map_df = apply_normalization(combined_df)
     norm_map_df["term_id"] = normalized_df.loc[norm_map_df.index, "term_id"]
     ```
   - Step 5: Deduplicate within entity_type:
     ```python
     dedup_df, dedup_map_df = deduplicate_within_entity_type(normalized_df)
     ```
   - Step 6: LLM classify non-authoritative terms:
     ```python
     if not mock:
         classified_df = self.classifier.classify(dedup_df)
     else:
         classified_df = self._mock_classify(dedup_df)
     ```
   - Step 7: Export CSVs:
     ```python
     self._export_csvs(classified_df, norm_map_df, dedup_map_df)
     ```
   - Step 8: Generate report:
     ```python
     stats = generate_term_inventory_report(classified_df, norm_map_df)
     ```
   - Log elapsed time and summary stats
   - Return stats dict

3. `_mock_classify(df: pd.DataFrame) -> pd.DataFrame`:
   - For non-authoritative terms, set `medical_domain = "unknown"`, `needs_human_review = True`
   - Preserve authoritative entity_type values

4. `_export_csvs(df, norm_map, dedup_map)`:
   - Export `medical_term_inventory.csv` with all columns
   - Export `term_normalization_map.csv` (norm_map with term_id)
   - Export `human_review_terms.csv`: rows where `review_status in ["not_verified", "needs_review"]` OR `llm_generated_candidate == True`
   - Export `term_sources.csv`: aggregate by source_name (term_count, entity_types, authoritative flag)
   - All files go to `config.output_dir`
</action>
  <verify>
python -c "
from src.term_inventory.builder import InventoryBuilder
from src.term_inventory.schemas import InventoryConfig
config = InventoryConfig()
builder = InventoryBuilder(config)
print('InventoryBuilder instantiated OK')
# Verify all loaders initialized
print(f'ICD10 loader: {builder.icd10_loader.__class__.__name__}')
print(f'RxNorm loader: {builder.rxnorm_loader.__class__.__name__}')
print(f'NLM loader: {builder.nlm_lab_loader.__class__.__name__}')
print(f'openFDA loader: {builder.openfda_loader.__class__.__name__}')
print(f'Abbreviation loader: {builder.abbreviation_loader.__class__.__name__}')
print(f'ViMedCSS seed loader: {builder.vimedcss_seed_loader.__class__.__name__}')
"
</verify>
  <done>InventoryBuilder orchestrates the full pipeline: load → normalize → deduplicate → classify → export. All loaders initialized in __init__.</done>
</task>

<task type="auto">
  <name>Task 2: Create reporter module for term inventory statistics</name>
  <files>src/term_inventory/reporter.py</files>
  <action>
Create `src/term_inventory/reporter.py`:

```python
"""Term inventory report generator for Phase 6b."""
import os
from typing import Dict, Any
import pandas as pd
from src.shared.logging import setup_logger

logger = setup_logger("term_inventory.reporter")
```

Implement `generate_term_inventory_report(df, norm_map) -> Dict[str, Any]`:

1. Compute statistics:
   - Total unique terms
   - Terms by entity_type (distribution table)
   - Terms by source_name (distribution table)
   - Authoritative vs non-authoritative count
   - LLM-generated candidate count
   - Terms needing human review count
   - Normalization transformation rate
   - Deduplication rate

2. Generate `reports/term_inventory_report.md` with sections:
   - Summary statistics table
   - Entity type distribution
   - Source distribution
   - Verification status (verified / needs_review / not_verified)
   - Normalization statistics
   - Vietnamese narrative explanation

3. Return stats dict with:
   - total_terms, authoritative_count, llm_candidate_count, review_queue_count
   - entity_type_distribution, source_distribution
   - normalization_map_count, deduplication_count

Log the report path.
</action>
  <verify>
python -c "from src.term_inventory.reporter import generate_term_inventory_report; print('reporter imported OK')"
</verify>
  <done>Reporter generates term_inventory_report.md with Vietnamese narrative, statistics tables, and distribution breakdowns.</done>
</task>

<task type="auto">
  <name>Task 3: Wire CLI build-inventory to InventoryBuilder</name>
  <files>src/term_inventory/cli.py</files>
  <read_first>src/term_inventory/builder.py</read_first>
  <action>
Update `src/term_inventory/cli.py` `run_build_inventory()`:

Replace the placeholder implementation (Plan 01 Task 4) with the full wiring:

```python
def run_build_inventory(args) -> None:
    """Run the full medical term inventory build pipeline."""
    from src.term_inventory.schemas import InventoryConfig
    from src.term_inventory.builder import InventoryBuilder

    logger.info("Starting medical term inventory build...")
    logger.info(f"Mode: {'MOCK' if args.mock else 'FULL'}")
    
    # Load config
    config = InventoryConfig()
    
    # Override with CLI args
    if args.output_dir:
        config.output_dir = args.output_dir
    
    # Create builder
    builder = InventoryBuilder(config)
    
    # Run pipeline
    stats = builder.build(mock=args.mock, limit=args.limit)
    
    # Print summary
    print("\n" + "=" * 60)
    print("Medical Term Inventory Build Complete")
    print("=" * 60)
    print(f"Total terms:        {stats['total_terms']}")
    print(f"Authoritative:       {stats['authoritative_count']}")
    print(f"LLM candidates:     {stats['llm_candidate_count']}")
    print(f"Review queue:       {stats['review_queue_count']}")
    print(f"Normalization map:   {stats['normalization_map_count']} transformations")
    print(f"Elapsed:            {stats.get('elapsed_seconds', 'N/A')}s")
    print("=" * 60)
    print(f"Output: {config.output_dir}/")
    print(f"Report: reports/term_inventory_report.md")
```

Also update `build_arg_parser()` if needed to add the `--limit` argument.

Add the subcommand registration to `src/cli.py`:
```python
# Add this inside the main CLI argument parser setup in src/cli.py
from src.term_inventory.cli import register_build_inventory_parser

def main():
    parser = argparse.ArgumentParser(...)
    subparsers = parser.add_subparsers(dest="command", help="...")
    
    # Existing subcommands...
    
    # Add term inventory subcommand
    build_inv_subparser = subparsers.add_parser(
        "build-inventory",
        help="Build medical term inventory from ICD-10 + supplementary lexicons"
    )
    build_inv_subparser.add_argument("--mock", action="store_true", ...)
    build_inv_subparser.add_argument("--full", action="store_true", ...)
    build_inv_subparser.add_argument("--output-dir", type=str, ...)
    build_inv_subparser.add_argument("--limit", type=int, ...)
```

Follow the existing CLI registration pattern in `src/cli.py`.
</action>
  <verify>
python -c "
import argparse
from src.term_inventory.cli import build_arg_parser, run_build_inventory
parser = build_arg_parser()
args = parser.parse_args(['build-inventory', '--mock', '--limit', '5'])
print('CLI args parsed OK:', args)
print('Mock:', args.mock)
print('Limit:', args.limit)
"
</verify>
  <done>CLI run_build_inventory() wires to InventoryBuilder.build(). Full pipeline executable with build-inventory --mock --limit 5.</done>
</task>

</tasks>

<verification>
python -c "
from src.term_inventory.builder import InventoryBuilder
from src.term_inventory.schemas import InventoryConfig
from src.term_inventory.reporter import generate_term_inventory_report
import pandas as pd

# Smoke test: mock pipeline
config = InventoryConfig()
builder = InventoryBuilder(config)

# Verify all methods exist
assert hasattr(builder, 'build')
assert hasattr(builder, '_mock_classify')
assert hasattr(builder, '_export_csvs')
print('InventoryBuilder methods OK')

# Verify reporter
report = generate_term_inventory_report(pd.DataFrame(), pd.DataFrame())
assert 'total_terms' in report
assert 'authoritative_count' in report
print('generate_term_inventory_report OK')
"
</verification>

<success_criteria>
- InventoryBuilder.build() orchestrates the full pipeline: load → concat → assign term_id → normalize → deduplicate → LLM classify → export
- All 6 loaders instantiated and called in correct order
- --mock mode uses _mock_classify() and truncates to limit
- 4 CSV files written to config.output_dir
- term_inventory_report.md written to reports/
- CLI build-inventory command works with --mock --full --output-dir --limit flags
- Pipeline produces valid output when Phase 1 and Phase 6a outputs exist
</success_criteria>

<output>
Create `.planning/phases/06B-medical-term-inventory-extended/06B-05-SUMMARY.md` when done
</output>
