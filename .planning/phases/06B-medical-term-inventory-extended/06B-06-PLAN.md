---
phase: "06B"
plan: "06"
type: execute
wave: 6
depends_on: ["06B-02", "06B-03", "06B-04", "06B-05"]
files_modified:
  - "tests/test_term_inventory_normalizer.py"
  - "tests/test_term_inventory_loaders.py"
autonomous: true
requirements:
  - "FR2-02"
  - "FR2-05"
  - "FR2-06"
---

<objective>
Create test scaffolding for the normalizer and loaders. This plan completes after Plan 05 (builder/reporter integration) and provides the test coverage that validates the pipeline outputs. When this plan completes, all four required output files are generated and tested.

Purpose: Comprehensive tests ensure the term inventory pipeline remains reliable as changes are made.
Output: `tests/test_term_inventory_normalizer.py`, `tests/test_term_inventory_loaders.py`.
</objective>

<execution_context>
@$HOME/.cursor/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/phases/06B-medical-term-inventory-extended/06B-05-PLAN.md
@tests/test_auditor.py

## Output File Schemas (FR2-06)

### term_sources.csv
Columns: `source_name, source_url, source_license, entity_types_provided, term_count, authoritative`

### human_review_terms.csv
Columns: `term_id, term_original, term_normalized, entity_type, medical_domain, source_name, review_status, llm_generated_candidate, needs_human_review_reason`

Where `needs_human_review_reason` is populated from:
- Confidence < 0.80 from LLM classification
- `uncertainty_reason` from LLM response
- "Flagged for human review" if manually tagged

## Reporter Sections

The report should include:
1. Executive summary (total terms, sources, entity types)
2. Entity type distribution table
3. Source coverage table (which entity types each source provides)
4. Verification status breakdown (verified / needs_review / not_verified)
5. LLM candidate summary
6. Normalization statistics
7. Recommendations for next steps (Phase 6c coverage audit)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create test scaffolding for normalizer and loaders</name>
  <files>
    tests/test_term_inventory_normalizer.py
    tests/test_term_inventory_loaders.py
  </files>
  <read_first>tests/test_auditor.py</read_first>
  <action>
Create `tests/test_term_inventory_normalizer.py`:

```python
"""Tests for src.term_inventory.normalizer module."""
import pytest
import pandas as pd
from src.term_inventory.normalizer import (
    normalize_term,
    normalize_batch,
    apply_normalization,
    deduplicate_within_entity_type,
    create_deduplication_report,
    GREEK_TO_ASCII,
)
```

Test cases:

1. `test_greek_to_ascii()`:
   - "β-blocker" → "beta-blocker"
   - "α-thalassemia" → "alpha-thalassemia"
   - "μg" → "mu" (or "mcg" if unit suffix applied)
   - "γ-globulin" → "gamma-globulin"

2. `test_nfc_normalization()`:
   - "metformin\u0301" → "metformin" (combining acute accent)
   - "café" (with combining accent) → "cafe"

3. `test_case_folding()`:
   - "METFORMIN" → "metformin"
   - "DiAbEtEs" → "diabetes"

4. `test_unit_normalization()`:
   - "insulin 100units" → contains "unit"
   - "metformin 500mg" → contains "mg"

5. `test_apply_normalization()`:
   - DataFrame with 3 rows → produces normalized DataFrame + normalization_map
   - Only rows with transformations appear in normalization_map

6. `test_deduplicate_same_entity_type()`:
   - Same entity_type, same normalized form → 1 row kept
   - Verified source wins over needs_review

7. `test_deduplicate_cross_entity_type()`:
   - Same normalized form, different entity_type → 2 rows kept
   - "insulin" as drug AND biomarker → both preserved

8. `test_deduplication_rate_warning()`:
   - Mock high deduplication (>30%) → check warning is logged

---

Create `tests/test_term_inventory_loaders.py`:

```python
"""Tests for src.term_inventory.loaders module."""
import pytest
import pandas as pd
from src.term_inventory.loaders import (
    BaseLoader,
    Icd10BackboneLoader,
    RxNormLoader,
    NlmLabLoader,
    OpenFdaDeviceLoader,
    AbbreviationLoader,
    VimedcssSeedLoader,
)
from src.term_inventory.schemas import InventoryConfig
```

Test cases:

1. `test_base_loader_interface()`:
   - All loaders inherit from BaseLoader
   - All loaders have `load()` method returning DataFrame

2. `test_icd10_backbone_loader_columns()`:
   - Mock the ICD-10 CSV path
   - After load(), DataFrame has required columns: term_original, entity_type, source_name, review_status

3. `test_abbreviation_loader_produces_expansions()`:
   - Load abbreviations ECG, MRI, CT
   - Result has >= 6 rows (abbreviation + expansion for each)
   - Contains "electrocardiogram" and "magnetic resonance imaging"

4. `test_vimedcss_seed_loader_missing_file()`:
   - Point to non-existent path
   - Raises FileNotFoundError

5. `test_all_loaders_required_cols()`:
   - Each loader's output has all REQUIRED_COLS
   - Verify term_original, entity_type, source_name, review_status present

6. `test_abbreviation_source_name()`:
   - All abbreviation rows have source_name = "abbreviation_list"
</action>
  <verify>
cd /home/thanhnndev/develop/projects/vimedcss-eval-pipeline && python -m pytest tests/test_term_inventory_normalizer.py tests/test_term_inventory_loaders.py -v --tb=short 2>&1 | tail -30
</verify>
  <done>Test files scaffolded. All tests pass.</done>
</task>

</tasks>

<verification>
cd /home/thanhnndev/develop/projects/vimedcss-eval-pipeline && python -m pytest tests/test_term_inventory_normalizer.py tests/test_term_inventory_loaders.py -v --tb=short 2>&1 | tail -30
</verification>

<success_criteria>
- tests/test_term_inventory_normalizer.py created with ≥8 test cases covering Greek-to-ASCII, NFC, case folding, unit normalization, deduplication
- tests/test_term_inventory_loaders.py created with ≥6 test cases covering BaseLoader interface, column requirements, abbreviation expansions, file missing errors
- All pytest tests pass
</success_criteria>

<output>
Create `.planning/phases/06B-medical-term-inventory-extended/06B-06-SUMMARY.md` when done
</output>
