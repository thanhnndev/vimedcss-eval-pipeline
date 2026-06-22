---
phase: "06B"
plan: "06"
type: execute
wave: 4
depends_on: ["06B-02", "06B-03", "06B-04"]
files_modified:
  - "src/term_inventory/reporter.py"
  - "src/term_inventory/builder.py"
  - "tests/test_term_inventory_normalizer.py"
  - "tests/test_term_inventory_loaders.py"
autonomous: true
requirements:
  - "FR2-02"
  - "FR2-05"
  - "FR2-06"
---

<objective>
Complete the reporter module, finalize the human_review_terms.csv export logic (FR2-06), wire term_sources.csv generation into the builder, and create test scaffolding for the normalizer and loaders. This is the final plan — when it completes, all four required output files are generated and tested.

Purpose: The reporter delivers the human-readable summary; human_review_terms.csv is the gate for data quality; term_sources.csv provides the provenance audit trail.
Output: `reports/term_inventory_report.md`, `data/terms/human_review_terms.csv`, `data/terms/term_sources.csv`, test files for normalizer and loaders.
</objective>

<execution_context>
@$HOME/.cursor/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@src/term_inventory/reporter.py
@src/term_inventory/builder.py
@.planning/phases/06B-medical-term-inventory-extended/06B-02-PLAN.md
@.planning/phases/06B-medical-term-inventory-extended/06B-03-PLAN.md
@.planning/phases/06B-medical-term-inventory-extended/06B-05-PLAN.md

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
  <name>Task 1: Complete reporter and human_review_terms export</name>
  <files>
    src/term_inventory/reporter.py
    src/term_inventory/builder.py
  </files>
  <action>
Complete `src/term_inventory/reporter.py` with full implementation:

```python
def generate_term_inventory_report(df: pd.DataFrame, norm_map: pd.DataFrame) -> Dict[str, Any]:
    """Generate term inventory report with Vietnamese narrative."""
```

Implement these sections:

1. **Statistics computation**:
   - `total_terms = len(df)`
   - `authoritative_count = (df["source_name"].isin(["icd10", "rxnorm", "openfda"])).sum()`
   - `llm_candidate_count = df["llm_generated_candidate"].sum()`
   - `review_queue_count = ((df["review_status"] == "needs_review") | (df["llm_generated_candidate"] == True)).sum()`
   - `normalization_map_count = len(norm_map)`
   - `entity_type_dist = df["entity_type"].value_counts().to_dict()`
   - `source_dist = df["source_name"].value_counts().to_dict()`

2. **term_sources.csv generation**:
   ```python
   source_rows = []
   for source_name, grp in df.groupby("source_name"):
       source_rows.append({
           "source_name": source_name,
           "source_url": grp["source_url"].iloc[0] if pd.notna(grp["source_url"].iloc[0]) else "",
           "source_license": get_source_license(source_name),
           "entity_types_provided": ";".join(sorted(grp["entity_type"].unique())),
           "term_count": len(grp),
           "authoritative": source_name in {"icd10", "rxnorm", "openfda"},
       })
   sources_df = pd.DataFrame(source_rows)
   sources_df.to_csv(os.path.join(config.output_dir, "term_sources.csv"), index=False)
   ```

3. **human_review_terms.csv generation**:
   ```python
   review_df = df[
       (df["review_status"] == "needs_review") |
       (df["review_status"] == "not_verified") |
       (df["llm_generated_candidate"] == True)
   ][["term_id", "term_original", "term_normalized", "entity_type",
       "medical_domain", "source_name", "review_status",
       "llm_generated_candidate"]].copy()
   review_df["needs_human_review_reason"] = review_df.apply(
       lambda r: _get_review_reason(r), axis=1
   )
   review_df.to_csv(os.path.join(config.output_dir, "human_review_terms.csv"), index=False)
   ```

4. **`_get_review_reason(row) -> str`**:
   - If `llm_generated_candidate == True`: "LLM-generated candidate — requires external source verification"
   - If `review_status == needs_review`: "Confidence below threshold or flagged by LLM"
   - If `review_status == not_verified`: "Non-authoritative source — manual review required"
   - Otherwise: "Requires verification"

5. **`get_source_license(source_name) -> str`**:
   - icd10 → "Public Domain (WHO)"
   - rxnorm → "Public Domain (NLM)"
   - openfda → "Public Domain (FDA)"
   - nlm_lab → "Public Domain (NLM)"
   - abbreviation_list → "Project Internal"
   - vimedcss_seed → "ViMedCSS Dataset License"
   - llm_generated → "N/A (generated)"
   - unknown → "Unknown"

6. **Report markdown generation** — produce Vietnamese narrative with:
   - Summary statistics in table format
   - Entity type distribution bar chart description
   - Source distribution table
   - Verification status pie description
   - Recommendations for Phase 6c coverage audit

Return stats dict. Log report path.

---

Update `src/term_inventory/builder.py` `_export_csvs()` to call reporter:
```python
def _export_csvs(self, df, norm_map, dedup_map):
    # medical_term_inventory.csv
    df.to_csv(os.path.join(self.config.output_dir, "medical_term_inventory.csv"), index=False)
    
    # term_normalization_map.csv
    norm_map.to_csv(os.path.join(self.config.output_dir, "term_normalization_map.csv"), index=False)
    
    # term_sources.csv + human_review_terms.csv via reporter
    stats = generate_term_inventory_report(df, norm_map)
    
    logger.info(f"Exported 4 CSV files to {self.config.output_dir}")
```

Make sure `generate_term_inventory_report` is called with the config output_dir so it can write term_sources.csv and human_review_terms.csv.
</action>
  <verify>
python -c "
from src.term_inventory.reporter import generate_term_inventory_report, _get_review_reason, get_source_license
import pandas as pd

# Test _get_review_reason
row = pd.Series({'llm_generated_candidate': True, 'review_status': 'not_verified'})
reason = _get_review_reason(row)
assert 'LLM-generated' in reason, f'Got: {reason}'
print('_get_review_reason test passed')

# Test get_source_license
assert get_source_license('icd10') == 'Public Domain (WHO)'
assert get_source_license('rxnorm') == 'Public Domain (NLM)'
assert get_source_license('openfda') == 'Public Domain (FDA)'
print('get_source_license test passed')

# Test generate_term_inventory_report
df = pd.DataFrame([
    {'term_id': 't1', 'term_original': 'metformin', 'entity_type': 'drug', 'source_name': 'rxnorm', 'review_status': 'verified', 'llm_generated_candidate': False},
    {'term_id': 't2', 'term_original': 'β-blocker', 'entity_type': 'drug', 'source_name': 'llm_generated', 'review_status': 'not_verified', 'llm_generated_candidate': True},
])
norm_map = pd.DataFrame([{'raw_form': 'β-blocker', 'normalized_form': 'beta-blocker'}])
stats = generate_term_inventory_report(df, norm_map)
assert stats['total_terms'] == 2
assert stats['authoritative_count'] == 1
assert stats['llm_candidate_count'] == 1
assert stats['review_queue_count'] == 1
print('generate_term_inventory_report test passed')
print(f'Stats: {stats}')
"
</verify>
  <done>Reporter generates term_sources.csv and human_review_terms.csv. All FR2-06 output files complete. Vietnamese narrative report generated.</done>
</task>

<task type="auto">
  <name>Task 2: Create test scaffolding for normalizer and loaders</name>
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
python -c "
from src.term_inventory.reporter import generate_term_inventory_report, get_source_license
from src.term_inventory.builder import InventoryBuilder
from src.term_inventory.schemas import InventoryConfig
import pandas as pd

# Final integration check
config = InventoryConfig()
builder = InventoryBuilder(config)

# Verify builder has all methods
assert hasattr(builder, 'build')
assert hasattr(builder, '_export_csvs')
print('Builder final check: OK')

# Verify reporter
df = pd.DataFrame([{'term_id': 't1', 'term_original': 'metformin', 'term_normalized': 'metformin', 'entity_type': 'drug', 'medical_domain': 'unknown', 'source_name': 'rxnorm', 'source_url': 'https://rxnav.nlm.nih.gov', 'review_status': 'verified', 'llm_generated_candidate': False}])
norm = pd.DataFrame()
stats = generate_term_inventory_report(df, norm)
assert stats['total_terms'] == 1
assert stats['authoritative_count'] == 1
print('Reporter final check: OK')
print('All FR2-06 output files validated')
"
</verification>

<success_criteria>
- generate_term_inventory_report() writes term_sources.csv and human_review_terms.csv to config.output_dir
- term_sources.csv has columns: source_name, source_url, source_license, entity_types_provided, term_count, authoritative
- human_review_terms.csv has columns: term_id, term_original, term_normalized, entity_type, medical_domain, source_name, review_status, llm_generated_candidate, needs_human_review_reason
- All LLM-generated candidates appear in human_review_terms.csv
- Reporter generates Vietnamese narrative in reports/term_inventory_report.md
- tests/test_term_inventory_normalizer.py created with ≥8 test cases
- tests/test_term_inventory_loaders.py created with ≥6 test cases
- All pytest tests pass
</success_criteria>

<output>
Create `.planning/phases/06B-medical-term-inventory-extended/06B-06-SUMMARY.md` when done
</output>
